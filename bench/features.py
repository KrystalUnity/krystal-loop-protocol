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
from klp.sandbox import Sandbox  # noqa: E402
from klp.snapshot import GIT_SAFE as GIT, Snapshots  # noqa: E402
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


def hidden_grade(env_dir: Path, scratch: Path, task: dict, candidate: bytes | None = None,
                 reference: Path | None = None) -> dict:
    """Grade one candidate patch on a pristine checkout with the hidden tests. Models never see this."""
    ws = scratch
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    sh("cp", "-a", str(env_dir / "ws/repo"), str(ws / "repo"))
    shutil.copy(task["tests_patch"], ws / "tests.patch")
    steps = ["true"]
    if candidate:
        (ws / "candidate.patch").write_bytes(candidate)
        steps.append(f"{GIT} apply --binary --whitespace=nowarn /workspace/candidate.patch")
    if reference:
        shutil.copy(reference, ws / "feature.patch")
        steps.append("(git apply --ignore-whitespace --ignore-space-change /workspace/feature.patch "
                     "|| git apply --3way /workspace/feature.patch)")
    # Hidden tests replace whatever the candidate did to the same test files.
    for path in task["patched_test_files"]:
        steps.append(f"(git cat-file -e {task['commit']}:{path} 2>/dev/null && {GIT} checkout -q {task['commit']} -- {path} "
                     f"|| rm -f {path})")
    steps.append("(git apply --ignore-whitespace --ignore-space-change /workspace/tests.patch "
                 "|| git apply --3way /workspace/tests.patch)")
    sandbox = box(ws, env_dir)
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
        without = hidden_grade(env_dir, scratch / "without", task)
        gold = hidden_grade(env_dir, scratch / "gold", task, reference=Path(task["gold_patch"]))
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

# name: (worker model, critic model, arm whose candidates it reviews, row label, acceptance file)
ARMS = {
    "frontier-solo": ("frontier", None, None, "Frontier model alone (gpt-6.1-sol)", False),
    "astra-solo": ("astra", None, None, "Heavy model alone (gpt-6-astra)", False),
    "worker": ("worker", None, None, "Low-cost worker alone (deepseek-flash)", False),
    "klp-sol": ("worker", "critic", "worker", "KLP Standard, gpt-6.1-sol critic", False),
    "klp-astra": ("worker", "critic_astra", "worker", "KLP Standard, gpt-6-astra critic", False),
    "klp-terra": ("worker", "critic_terra", "worker", "KLP Standard, gpt-6.1-terra critic", False),
    "klp": ("worker", "critic", None, "KLP Standard (single pass)", False),
    # klp-standard/v0.2 on the same candidates as the arms above
    "v2-sol": ("worker", "critic", "worker", "KLP Standard v0.2, gpt-6.1-sol critic", False),
    "v2a-sol": ("worker", "critic", "worker", "KLP Standard v0.2 with acceptance file, gpt-6.1-sol critic", True),
    "v2-grok": ("worker", "critic_grok", "worker", "KLP Standard v0.2, grok-4.7 critic", False),
    "v2a-grok": ("worker", "critic_grok", "worker", "KLP Standard v0.2 with acceptance file, grok-4.7 critic", True),
    "v2-argon": ("worker", "critic_argon", "worker", "KLP Standard v0.2, Gemini 4 Argon critic on a subscription CLI", False),
    "v2a-argon": ("worker", "critic_argon", "worker", "KLP Standard v0.2 with acceptance file, Gemini 4 Argon critic on a subscription CLI", True),
    "v2-kimi": ("worker", "critic_kimi", "worker", "KLP Standard v0.2, Kimi K3.1 Pro critic on a subscription CLI", False),
    "v2a-kimi": ("worker", "critic_kimi", "worker", "KLP Standard v0.2 with acceptance file, Kimi K3.1 Pro critic on a subscription CLI", True),
    "v2-qwen": ("worker", "critic_qwen", "worker", "KLP Standard v0.2, Qwen 3.8 Max critic on a subscription CLI", False),
    "v2a-qwen": ("worker", "critic_qwen", "worker", "KLP Standard v0.2 with acceptance file, Qwen 3.8 Max critic on a subscription CLI", True),
    # a fresh set of worker candidates, built and reviewed under v0.2
    "worker-3": ("worker", None, None, "Low-cost worker alone, run 3 (deepseek-flash)", False),
    "klp-3": ("worker", "critic", "worker-3", "KLP Standard v0.2, run 3, gpt-6.1-sol critic", False),
    "klp-3a": ("worker", "critic", "worker-3", "KLP Standard v0.2 with acceptance file, run 3, gpt-6.1-sol critic", True),
}


def run_one(work: Path, ledger: Ledger, task: dict, arm: str, limits: Limits) -> dict:
    out = work / "runs" / arm / task["id"]
    if (out / "result.json").exists():
        return json.loads((out / "result.json").read_text())
    env_dir = work / "envs" / task["env"]
    worker_key, critic_key, reuse, _, acceptance = ARMS[arm]
    check = f"{PYTEST} -x {' '.join(task['test_files'])}"
    statement = Path(task["statement"]).read_text().strip()
    prompt = f"{statement}\n\nExisting tests that must keep passing:\n$ {check}"
    scope = f"{arm}/{task['id']}"
    resume, known = None, {}
    try:
        if reuse:
            # Review the worker arm's exact candidate: same files, same snapshot store, same session.
            source = work / "runs" / reuse / task["id"]
            built = json.loads((source / "result.json").read_text())
            if built["state"] == "harness_error":
                raise RuntimeError(f"arm {reuse} has no candidate for this task")
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir(parents=True)
            sh("cp", "-a", str(source / "ws"), str(out / "ws"))
            sh("cp", "-a", str(source / "snapshots"), str(out / "snapshots"))
            resume = dict(receipt=json.loads((source / "receipt.json").read_text()),
                          messages=json.loads((source / "worker-transcript.json").read_text()))
            known = built["grades"]
            ws = out / "ws"
        else:
            ws = fresh_workspace(env_dir, out / "ws")
        receipt = run_standard(ledger=ledger, worker=Model.from_spec(MODELS[worker_key]),
                               critic=Model.from_spec(MODELS[critic_key]) if critic_key else None,
                               sandbox=box(ws, env_dir), task=prompt, checks=[check], scope=scope, limits=limits,
                               out_dir=out, task_id=task["id"], project_revision=task["commit"], resume=resume,
                               acceptance=acceptance)
    except Exception as error:  # a harness fault is a recorded failure, never a silent skip
        out.mkdir(parents=True, exist_ok=True)
        result = dict(task=task["id"], arm=arm, state="harness_error", error=f"{type(error).__name__}: {error}"[:400],
                      grades={}, usd=str(ledger.spent(scope=scope)), effort=ledger.summary(scope=scope))
        (out / "result.json").write_text(json.dumps(result, indent=1))
        return result
    grades, snapshots = dict(known), Snapshots(box(ws, env_dir), out / "snapshots")
    for candidate in receipt["candidates"]:
        if candidate["revision"] not in grades:
            patch = snapshots.patch(receipt["base_revision"], candidate["revision"])
            grades[candidate["revision"]] = hidden_grade(env_dir, out / "grade", task, candidate=patch)
    done = receipt["completion"]
    first = receipt["candidates"][0]["revision"] if receipt["candidates"] else None
    result = dict(task=task["id"], arm=arm, state=done["state"], final_revision=done["final_revision"],
                  solved=bool(grades.get(done["final_revision"], {}).get("passed")),
                  first_candidate_solved=bool(grades.get(first, {}).get("passed")),
                  grades=grades, usd=done["measured_effort"]["usd"], seconds=done["measured_effort"]["seconds"],
                  effort=done["measured_effort"]["by_role"],
                  reviews=[dict(verdict=r["verdict"], packet_bytes=r["packet_bytes"],
                                dispositions=[f["disposition"] for f in r["findings"] if not f.get("carried")],
                                acceptance=(r.get("acceptance") or {}).get("result"),
                                acceptance_findings=sum(f.get("source") == "acceptance" and not f.get("carried")
                                                        for f in r["findings"]),
                                withdrawn=len(r.get("withdrawn") or [])) for r in receipt["reviews"]],
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
    spent_before = ledger.spent()
    ledger.cap += spent_before  # the cap is for this invocation; earlier spend stays on the ledger
    print(f"{len(tasks)} tasks x {len(arms)} arms, cap ${cap} for this run, ledger so far ${spent_before:.4f}", flush=True)
    # Arms that review the worker arm's candidates wait until those candidates exist.
    for wave in ([a for a in arms if not ARMS[a][2]], [a for a in arms if ARMS[a][2]]):
        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            futures = [pool.submit(run_one, work, ledger, t, a, limits) for t in tasks for a in wave]
            for future in concurrent.futures.as_completed(futures):
                r = future.result()
                print(f"  {r['arm']:14s} {r['task']:38s} {r['state']:17s} solved={r.get('solved')} "
                      f"first={r.get('first_candidate_solved')} ${float(r['usd']):.4f} "
                      f"run=${ledger.spent() - spent_before:.3f}", flush=True)
    report(work)


# ---------------------------------------------------------------- report

def role_usd(result: dict, roles: tuple | None = None) -> D:
    return sum((D(v["usd"]) for k, v in result.get("effort", {}).items() if roles is None or k in roles), D(0))


def report(work: Path, arms: list[str] | None = None) -> dict:
    """One row per arm over the tasks every reported arm finished. Review arms include their worker's cost."""
    rows = [json.loads(p.read_text()) for p in sorted((work / "runs").glob("*/*/result.json"))]
    by_arm, every = {}, {}
    for r in rows:
        every.setdefault(r["arm"], {})[r["task"]] = r
        if r["arm"] in ARMS and (arms is None or r["arm"] in arms):
            by_arm.setdefault(r["arm"], {})[r["task"]] = r
    common = sorted(set.intersection(*[set(v) for v in by_arm.values()])) if by_arm else []
    table, reviews = {}, {}
    for arm in [a for a in ARMS if a in by_arm]:
        items = [by_arm[arm][t] for t in common]
        reuse = ARMS[arm][2]
        built = every.get(reuse, {}) if reuse else {}
        cost = [D(r["usd"]) + (role_usd(built[r["task"]]) if reuse and r["task"] in built else D(0)) for r in items]
        solved, total = sum(bool(r.get("solved")) for r in items), sum(cost, D(0))
        table[ARMS[arm][3]] = dict(
            arm=arm, candidates_from=reuse, tasks=len(items), solved=solved, usd=str(total),
            unmetered_review_calls=sum(r.get("effort", {}).get("critic", {}).get("unmetered_calls", 0) for r in items),
            usd_per_task=str(total / len(items)) if items else None, usd_per_solved=str(total / solved) if solved else None,
            median_seconds=statistics.median([r.get("seconds", 0) for r in items]) if items else None,
            states=dict(sorted({s: sum(r["state"] == s for r in items) for s in {r["state"] for r in items}}.items())))
        if ARMS[arm][1]:
            if arm == "klp":  # single-pass arm: the worker's own pre-review result is a row too
                table["Low-cost worker alone (same runs, before review)"] = dict(
                    arm="klp:first-candidate", tasks=len(items), solved=sum(bool(r.get("first_candidate_solved")) for r in items),
                    usd=str(sum((role_usd(r, ("worker",)) for r in items), D(0))))
            reviews[arm] = dict(
                reviews=sum(len(r["reviews"]) for r in items),
                findings={d: sum(v["dispositions"].count(d) for r in items for v in r["reviews"])
                          for d in ("confirmed", "refuted", "unverified", "advisory")},
                acceptance={k: sum(v.get("acceptance") == k for r in items for v in r["reviews"])
                            for k in ("passed", "failed", "did not run")},
                acceptance_findings=sum(v.get("acceptance_findings", 0) for r in items for v in r["reviews"]),
                withdrawn=sum(v.get("withdrawn", 0) for r in items for v in r["reviews"]),
                repairs=sum(len(r["repairs"]) for r in items), repairs_kept=sum(bool(x["kept"]) for r in items for x in r["repairs"]),
                findings_closed=sum(x["closed"] for r in items for x in r["repairs"]),
                fixed_by_review=sorted(r["task"] for r in items if r["solved"] and not r["first_candidate_solved"]),
                broken_by_review=sorted(r["task"] for r in items if not r["solved"] and r["first_candidate_solved"]),
                usd_by_role={role: str(sum((role_usd(r, (role,)) for r in items), D(0))
                                       + (sum((role_usd(built[r["task"]]) for r in items if r["task"] in built), D(0))
                                          if reuse and role == "worker" else D(0)))
                             for role in ("worker", "critic", "repair")})
    out = dict(tasks_compared=len(common), arms=table, reviews=reviews)
    (work / "report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def reprice(work: Path) -> None:
    """Recompute every recorded cost from token usage and the current price list. Usage is never changed."""
    from klp.llm import load_prices, price, rates_at
    from klp.standard import render_receipt
    prices = load_prices()
    ledger_file = work / "ledger.jsonl"
    rows = [json.loads(line) for line in ledger_file.read_text().splitlines()]
    for row in rows:
        if row.get("usage") and row.get("metered") is not False:
            rates, row["tier"] = rates_at(prices.get(row["model"]), row["started"])
            usd = price(row["usage"], rates)
            row["usd"] = None if usd is None else str(usd)
    ledger_file.write_text("".join(json.dumps(r) + "\n" for r in rows))
    ledger = Ledger(ledger_file, 0)
    for result_file in sorted((work / "runs").glob("*/*/result.json")):
        result = json.loads(result_file.read_text())
        scope = f"{result['arm']}/{result['task']}"
        result["usd"], result["effort"] = str(ledger.spent(scope=scope)), ledger.summary(scope=scope)
        result_file.write_text(json.dumps(result, indent=1))
        receipt_file = result_file.with_name("receipt.json")
        if receipt_file.exists():
            receipt = json.loads(receipt_file.read_text())
            receipt["completion"]["measured_effort"].update(by_role=result["effort"], usd=result["usd"])
            receipt_file.write_text(json.dumps(receipt, indent=1))
            result_file.with_name("receipt.md").write_text(render_receipt(receipt))
    print(f"repriced {len(rows)} calls; total ${ledger.spent():.4f}")
    report(work)


def export(work: Path, out: Path, examples: list[str], arms_filter: list[str] | None = None) -> None:
    """Write the public evidence pack: per-run results, the call ledger and the report. No prompts or model text."""
    out.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((work / "tasks.json").read_text())
    rows = [json.loads(p.read_text()) for p in sorted((work / "runs").glob("*/*/result.json"))]
    if arms_filter:
        rows = [r for r in rows if r["arm"] in arms_filter]
    for row in rows:
        row["grades"] = {rev: dict(passed=g["passed"], stage=g["stage"]) for rev, g in row.get("grades", {}).items()}
    keep = ("id", "scope", "role", "model", "returned_model", "status", "usage", "usd", "tier", "metered", "seconds",
            "finish_reason")
    calls = [{k: r.get(k) for k in keep} for r in (json.loads(line) for line in (work / "ledger.jsonl").read_text().splitlines())]
    if arms_filter:
        calls = [c for c in calls if c["scope"].split("/")[0] in arms_filter]
    (out / "results.json").write_text(json.dumps(rows, indent=1) + "\n")
    (out / "ledger.jsonl").write_text("".join(json.dumps(c) + "\n" for c in calls))
    arms = sorted({r["arm"] for r in rows})
    (out / "report.json").write_text(json.dumps(report(work, arms), indent=1) + "\n")
    (out / "tasks.json").write_text(json.dumps(dict(
        dataset=tasks["dataset"], revision=tasks["revision"],
        tasks=[dict(id=t["id"], repository=json.loads((work / "envs" / t["env"] / "env.json").read_text())["url"],
                    commit=t["commit"], test_files=t["test_files"], validation=t["validation"]) for t in tasks["tasks"]]),
        indent=1) + "\n")
    (out / "models.json").write_text(json.dumps(MODELS, indent=1) + "\n")
    shutil.copy(Path(__file__).resolve().parents[1] / "klp" / "prices.json", out / "prices.json")
    for name in examples:  # "arm/task-id"
        source = work / "runs" / name / "receipt.md"
        if source.exists():
            (out / "receipts").mkdir(exist_ok=True)
            shutil.copy(source, out / "receipts" / (name.replace("/", "--") + ".md"))
    print(f"exported {len(rows)} run results and {len(calls)} call receipts to {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("prepare", "run", "report", "export", "reprice"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--arms", default="frontier-solo,worker,v2-sol",
                        help="comma-separated: " + ", ".join(ARMS))
    parser.add_argument("--cap", type=float, default=5.0, help="hard USD limit across the whole run")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--ids", default="")
    parser.add_argument("--max-steps", type=int, default=100)
    parser.add_argument("--task-cap", type=float, default=2.0)
    parser.add_argument("--repair-rounds", type=int, default=2)
    parser.add_argument("--out", type=Path, help="export: destination folder")
    parser.add_argument("--examples", default="", help="export: task ids whose receipts to include")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    if args.command == "prepare":
        prepare(args.work, args.jobs)
    elif args.command == "run":
        run(args.work, args.arms.split(","), args.cap, args.jobs, args.limit,
            [i for i in args.ids.split(",") if i], Limits(max_steps=args.max_steps, cost_usd=args.task_cap, repair_rounds=args.repair_rounds))
    elif args.command == "reprice":
        reprice(args.work)
    elif args.command == "export":
        export(args.work, args.out, [i for i in args.examples.split(",") if i],
               [a for a in args.arms.split(",") if a] if args.arms != parser.get_default("arms") else None)
    else:
        report(args.work, [a for a in args.arms.split(",") if a] if args.arms != parser.get_default("arms") else None)


if __name__ == "__main__":
    main()
