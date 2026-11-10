"""Public benchmark: real-repository feature tasks graded by hidden tests.

Tasks come from the public CooperBench dataset (https://github.com/cooperbench/CooperBench),
pinned to one revision. Each task is one feature in a real open-source repository at a fixed
commit, with a written specification and a test patch the models never see.

    python -m bench.features prepare --work ~/klp-bench          # fetch, build, validate
    python -m bench.features run --work ~/klp-bench --cap 60     # spend, with a hard cap
    python -m bench.features report --work ~/klp-bench

Arms:
    frontier-solo   a frontier model works alone
    klp             a low-cost worker under KLP Standard with a frontier critic
The low-cost worker's candidate before review is graded too, so the report shows the same
worker alone, and exactly what review and repair changed.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import shutil
import statistics
import subprocess
import sys
import time
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klp.llm import Ledger, Model  # noqa: E402
from klp.review import GIT  # noqa: E402
from klp.sandbox import Sandbox  # noqa: E402
from klp.standard import Limits, run_standard  # noqa: E402

DATASET_URL = "https://github.com/cooperbench/CooperBench.git"
DATASET_REVISION = "63b9d44d9f39a02fccf5bf0052db48a917a011fd"
SUITES = ("pallets_click_task", "pallets_jinja_task", "samuelcolvin_dirty_equals_task")
MODELS = json.loads(Path(__file__).with_name("models.json").read_text())
PYTEST = "python -m pytest -q -p no:cacheprovider"


def sh(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    done = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and done.returncode:
        raise RuntimeError(f"{' '.join(args[:4])}: {done.stderr.strip()[:500]}")
    return done.stdout


def python_binds(version: str) -> dict:
    """Read-only mounts that make a uv-managed interpreter visible inside the sandbox."""
    exe = Path(sh("uv", "python", "find", version).strip())
    home = exe.parents[1]
    if str(home.resolve()).startswith("/usr"):
        return {}
    root = home.parent if home.is_symlink() else home  # uv links cpython-3.11 -> cpython-3.11.x
    return {str(root): str(root)}


def box(workspace: Path, env_dir: Path, *, network: bool = False, build: bool = False) -> Sandbox:
    binds = python_binds(json.loads((env_dir / "env.json").read_text())["python"])
    venv = {str(env_dir / "venv"): "/venv"}
    return Sandbox(workspace, ro_binds={**binds, **({} if build else venv)},
                   rw_binds=venv if build else {}, path_prefix="/venv/bin", network=network)


# ---------------------------------------------------------------- prepare

def fetch_dataset(work: Path) -> Path:
    target = work / "CooperBench"
    if not (target / "dataset").exists():
        sh("git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", DATASET_URL, str(target))
        sh("git", "sparse-checkout", "init", "--cone", cwd=target)
        sh("git", "sparse-checkout", "set", *[f"dataset/{s}" for s in SUITES], cwd=target)
        sh("git", "checkout", "--quiet", DATASET_REVISION, cwd=target)
    return target / "dataset"


def read_task_folder(folder: Path) -> dict:
    docker = (folder / "Dockerfile").read_text()
    runner = (folder / "runner.sh").read_text()
    url = re.search(r"git clone (\S+?)(?:\.git)? repo", docker).group(1)
    commit = re.search(r"git checkout ([0-9a-f]{40})", docker).group(1)
    python = re.search(r"FROM python:(\d+\.\d+)", docker).group(1)
    tests = re.search(r"python -m pytest (.+?) -v", runner).group(1).split()
    return dict(url=url, commit=commit, python=python, test_files=tests)


def build_env(env_dir: Path, spec: dict) -> None:
    if (env_dir / "ready").exists():
        return
    shutil.rmtree(env_dir, ignore_errors=True)
    (env_dir / "ws").mkdir(parents=True)
    (env_dir / "env.json").write_text(json.dumps(spec))
    sh("git", "clone", "--quiet", spec["url"], str(env_dir / "ws/repo"))
    sh("git", "checkout", "--quiet", spec["commit"], cwd=env_dir / "ws/repo")
    sh("uv", "venv", "--quiet", "--seed", "--python", spec["python"], str(env_dir / "venv"))
    done = box(env_dir / "ws", env_dir, network=True, build=True).run(
        '(python -m pip install -q -e ".[test]" || python -m pip install -q -e .) '
        "&& python -m pip install -q pytest pytest-xdist pytest_mock", timeout=900)
    if done["returncode"] != 0:
        raise RuntimeError(f"environment build failed: {done['output'][-600:]}")
    (env_dir / "ready").write_text(time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))


def fresh_workspace(env_dir: Path, target: Path) -> Path:
    shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True)
    sh("cp", "-a", str(env_dir / "ws/repo"), str(target / "repo"))
    return target


def hidden_grade(env_dir: Path, scratch: Path, task: dict, revision: str | None, source: Path | None = None,
                 extra_patch: Path | None = None) -> dict:
    """Apply the hidden test patch to one revision and run the task's test files. Models never see this."""
    ws = scratch
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    sh("cp", "-a", str(source or env_dir / "ws/repo"), str(ws / "repo"))
    shutil.copy(task["tests_patch"], ws / "tests.patch")
    if extra_patch:
        shutil.copy(extra_patch, ws / "feature.patch")
    sandbox = box(ws, env_dir)
    steps = [f"{GIT} reset -q --hard {revision or 'HEAD'}", f"{GIT} clean -fdq"]
    if extra_patch:
        steps.append("(git apply --ignore-whitespace --ignore-space-change /workspace/feature.patch "
                     "|| git apply --3way /workspace/feature.patch)")
    # Hidden tests replace whatever the candidate did to the same test files.
    for path in task["patched_test_files"]:
        steps.append(f"(git cat-file -e {task['commit']}:{path} 2>/dev/null && {GIT} checkout -q {task['commit']} -- {path} "
                     f"|| rm -f {path})")
    steps.append("(git apply --ignore-whitespace --ignore-space-change /workspace/tests.patch "
                 "|| git apply --3way /workspace/tests.patch)")
    setup = sandbox.run(" && ".join(steps), limit=1500)
    if setup["returncode"] != 0:
        return dict(passed=False, stage="apply", output=setup["output"])
    run = sandbox.run(f"{PYTEST} {' '.join(task['test_files'])}", timeout=1200, limit=3000)
    shutil.rmtree(ws, ignore_errors=True)
    return dict(passed=run["returncode"] == 0, stage="tests", returncode=run["returncode"], output=run["output"][-1500:])


def prepare(work: Path, jobs: int) -> None:
    dataset = fetch_dataset(work)
    tasks, envs = [], {}
    for suite in SUITES:
        for folder in sorted((dataset / suite).glob("task*")):
            spec = read_task_folder(folder)
            key = f"{suite.removesuffix('_task')}-{folder.name}"
            envs[key] = spec
            for feature in sorted(folder.glob("feature*"), key=lambda p: int(p.name.removeprefix("feature"))):
                patch = (feature / "tests.patch").read_text()
                tasks.append(dict(id=f"{key}-{feature.name}", env=key, commit=spec["commit"],
                                  test_files=spec["test_files"], statement=str(feature / "feature.md"),
                                  tests_patch=str(feature / "tests.patch"), gold_patch=str(feature / "feature.patch"),
                                  patched_test_files=sorted(set(re.findall(r"^diff --git a/(\S+) b/", patch, re.M)))))
    for key, spec in envs.items():
        print(f"env {key}: python {spec['python']} {spec['url']}@{spec['commit'][:10]}", flush=True)
        build_env(work / "envs" / key, spec)

    def validate(task: dict) -> dict:
        env_dir, scratch = work / "envs" / task["env"], work / "scratch" / task["id"]
        base = box(fresh_workspace(env_dir, scratch / "base"), env_dir).run(
            f"{PYTEST} {' '.join(task['test_files'])}", timeout=1200, limit=600)
        without = hidden_grade(env_dir, scratch / "without", task, None)
        gold = hidden_grade(env_dir, scratch / "gold", task, None, extra_patch=Path(task["gold_patch"]))
        shutil.rmtree(scratch, ignore_errors=True)
        task["validation"] = dict(base_tests_pass=base["returncode"] == 0, hidden_fail_without_feature=not without["passed"],
                                  hidden_pass_with_reference=gold["passed"])
        task["valid"] = all(task["validation"].values())
        if not task["valid"]:
            task["validation"]["detail"] = (gold if not gold["passed"] else without if without["passed"] else base)["output"][-400:]
        print(f"  {task['id']}: {'ok' if task['valid'] else 'EXCLUDED ' + json.dumps(task['validation'])[:300]}", flush=True)
        return task

    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        tasks = list(pool.map(validate, tasks))
    (work / "tasks.json").write_text(json.dumps(dict(dataset=DATASET_URL, revision=DATASET_REVISION, tasks=tasks), indent=1))
    print(f"{sum(t['valid'] for t in tasks)} of {len(tasks)} tasks validated -> {work / 'tasks.json'}")


# ---------------------------------------------------------------- run

ARMS = {"frontier-solo": ("frontier", None), "klp": ("worker", "critic")}


def run_one(work: Path, ledger: Ledger, task: dict, arm: str, limits: Limits) -> dict:
    out = work / "runs" / arm / task["id"]
    if (out / "result.json").exists():
        return json.loads((out / "result.json").read_text())
    env_dir = work / "envs" / task["env"]
    ws = fresh_workspace(env_dir, out / "ws")
    worker_key, critic_key = ARMS[arm]
    check = f"{PYTEST} -x {' '.join(task['test_files'])}"
    statement = Path(task["statement"]).read_text().strip()
    prompt = f"{statement}\n\nExisting tests that must keep passing:\n$ {check}"
    scope = f"{arm}/{task['id']}"
    try:
        receipt = run_standard(ledger=ledger, worker=Model.from_spec(MODELS[worker_key]),
                               critic=Model.from_spec(MODELS[critic_key]) if critic_key else None,
                               sandbox=box(ws, env_dir), task=prompt, checks=[check], scope=scope, limits=limits,
                               out_dir=out, task_id=task["id"])
    except Exception as error:  # a harness fault is a recorded failure, never a silent skip
        result = dict(task=task["id"], arm=arm, state="harness_error", error=f"{type(error).__name__}: {error}"[:400],
                      grades={}, usd=str(ledger.spent(scope=scope)), effort=ledger.summary(scope=scope))
        (out / "result.json").write_text(json.dumps(result, indent=1))
        return result
    grades = {}
    for candidate in receipt["candidates"]:
        if candidate["revision"] not in grades:
            grades[candidate["revision"]] = hidden_grade(env_dir, out / "grade", task, candidate["revision"], source=ws / "repo")
    done = receipt["completion"]
    first = receipt["candidates"][0]["revision"] if receipt["candidates"] else None
    result = dict(task=task["id"], arm=arm, state=done["state"], final_revision=done["final_revision"],
                  solved=bool(grades.get(done["final_revision"], {}).get("passed")),
                  first_candidate_solved=bool(grades.get(first, {}).get("passed")),
                  grades=grades, usd=done["measured_effort"]["usd"], seconds=done["measured_effort"]["seconds"],
                  effort=done["measured_effort"]["by_role"],
                  reviews=[dict(verdict=r["verdict"], packet_bytes=r["packet_bytes"],
                                dispositions=[f["disposition"] for f in r["findings"]]) for r in receipt["reviews"]],
                  repairs=[dict(kept=r.get("kept"), closed=sum(p["closed"] for p in r["probes"]), probes=len(r["probes"]))
                           for r in receipt["repairs"]], errors=receipt["errors"])
    (out / "result.json").write_text(json.dumps(result, indent=1))
    return result


def run(work: Path, arms: list[str], cap: float, jobs: int, limit: int | None, ids: list[str] | None,
        limits: Limits) -> None:
    tasks = [t for t in json.loads((work / "tasks.json").read_text())["tasks"] if t["valid"]]
    if ids:
        tasks = [t for t in tasks if t["id"] in ids]
    if limit:
        tasks = tasks[:limit]
    ledger = Ledger(work / "ledger.jsonl", cap)
    jobs_list = [(t, a) for t in tasks for a in arms]
    print(f"{len(tasks)} tasks x {len(arms)} arms, cap ${cap}, already spent ${ledger.spent():.4f}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        futures = {pool.submit(run_one, work, ledger, t, a, limits): (t["id"], a) for t, a in jobs_list}
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            print(f"  {r['arm']:14s} {r['task']:38s} {r['state']:17s} solved={r.get('solved')} "
                  f"first={r.get('first_candidate_solved')} ${float(r['usd']):.4f} total=${ledger.spent():.3f}", flush=True)
    report(work)


# ---------------------------------------------------------------- report

def report(work: Path) -> dict:
    rows = [json.loads(p.read_text()) for p in sorted((work / "runs").glob("*/*/result.json"))]
    by_arm: dict = {}
    for r in rows:
        by_arm.setdefault(r["arm"], []).append(r)
    common = set.intersection(*[{r["task"] for r in v} for v in by_arm.values()]) if by_arm else set()
    table = {}

    def line(name: str, items: list, solved_key: str, usd) -> None:
        solved = sum(bool(r.get(solved_key)) for r in items)
        total = sum((usd(r) for r in items), D(0))
        table[name] = dict(tasks=len(items), solved=solved, solve_rate=round(solved / len(items), 4) if items else None,
                           usd=str(total), usd_per_task=str(total / len(items)) if items else None,
                           usd_per_solved=str(total / solved) if solved else None,
                           median_seconds=statistics.median([r.get("seconds", 0) for r in items]) if items else None)

    def role_usd(r: dict, roles: tuple) -> D:
        return sum((D(v["usd"]) for k, v in r.get("effort", {}).items() if k in roles), D(0))

    frontier = [r for r in by_arm.get("frontier-solo", []) if r["task"] in common]
    klp = [r for r in by_arm.get("klp", []) if r["task"] in common]
    if frontier:
        line("frontier model alone", frontier, "solved", lambda r: D(r["usd"]))
    if klp:
        line("low-cost worker alone", klp, "first_candidate_solved", lambda r: role_usd(r, ("worker",)))
        line("KLP Standard", klp, "solved", lambda r: D(r["usd"]))
    review = dict(
        reviews=sum(len(r["reviews"]) for r in klp), fail_verdicts=sum(v["verdict"] == "FAIL" for r in klp for v in r["reviews"]),
        findings={d: sum(v["dispositions"].count(d) for r in klp for v in r["reviews"])
                  for d in ("confirmed", "refuted", "unverified", "advisory")},
        repairs=sum(len(r["repairs"]) for r in klp), repairs_kept=sum(bool(x["kept"]) for r in klp for x in r["repairs"]),
        fixed_by_review=sorted(r["task"] for r in klp if r["solved"] and not r["first_candidate_solved"]),
        broken_by_review=sorted(r["task"] for r in klp if not r["solved"] and r["first_candidate_solved"]),
        usd_by_role={role: str(sum((role_usd(r, (role,)) for r in klp), D(0))) for role in ("worker", "critic", "repair")})
    states: dict = {}
    for r in rows:
        states.setdefault(r["arm"], {}).setdefault(r["state"], 0)
        states[r["arm"]][r["state"]] += 1
    out = dict(tasks_compared=len(common), arms=table, klp_review=review, states=states)
    (work / "report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def export(work: Path, out: Path, examples: list[str]) -> None:
    """Write the public evidence pack: per-run results, the call ledger and the report. No prompts or model text."""
    out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((work / "tasks.json").read_text())
    rows = [json.loads(p.read_text()) for p in sorted((work / "runs").glob("*/*/result.json"))]
    for row in rows:
        row["grades"] = {rev: dict(passed=g["passed"], stage=g["stage"]) for rev, g in row.get("grades", {}).items()}
    keep = ("id", "scope", "role", "model", "returned_model", "status", "usage", "usd", "seconds", "finish_reason")
    calls = [{k: r.get(k) for k in keep} for r in (json.loads(line) for line in (work / "ledger.jsonl").read_text().splitlines())]
    (out / "results.json").write_text(json.dumps(rows, indent=1) + "\n")
    (out / "ledger.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls))
    (out / "report.json").write_text(json.dumps(report(work), indent=1) + "\n")
    (out / "tasks.json").write_text(json.dumps(dict(
        dataset=tasks["dataset"], revision=tasks["revision"],
        tasks=[dict(id=t["id"], repository=json.loads((work / "envs" / t["env"] / "env.json").read_text())["url"],
                    commit=t["commit"], test_files=t["test_files"], validation=t["validation"]) for t in tasks["tasks"]]),
        indent=1) + "\n")
    (out / "models.json").write_text(json.dumps(MODELS, indent=1) + "\n")
    for name in examples:
        source = work / "runs" / "klp" / name / "receipt.md"
        if source.exists():
            (out / "receipts").mkdir(exist_ok=True)
            shutil.copy(source, out / "receipts" / f"{name}.md")
    print(f"exported {len(rows)} run results and {len(calls)} call receipts to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("prepare", "run", "report", "export"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--arms", default="frontier-solo,klp")
    parser.add_argument("--cap", type=float, default=5.0, help="hard USD limit across the whole run")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", default="")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--task-cap", type=float, default=2.0)
    parser.add_argument("--out", type=Path, help="export: destination folder")
    parser.add_argument("--examples", default="", help="export: task ids whose receipts to include")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.command == "prepare":
        prepare(args.work, args.jobs)
    elif args.command == "run":
        run(args.work, args.arms.split(","), args.cap, args.jobs, args.limit,
            [i for i in args.ids.split(",") if i], Limits(max_steps=args.max_steps, cost_usd=args.task_cap))
    elif args.command == "export":
        export(args.work, args.out, [i for i in args.examples.split(",") if i])
    else:
        report(args.work)


if __name__ == "__main__":
    main()
