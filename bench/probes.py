"""Re-run the critics' probes from a feature benchmark run against the dataset's reference solution.

A probe is the test a critic writes to back a finding: it fails on the candidate if the finding is real.
Each recorded probe runs twice in the sandbox, with no network:

  1. on the candidate the critic reviewed, to show the rerun reproduces the recorded outcome;
  2. on the reference solution the dataset ships with the task.

A probe that passes on the reference asks for behaviour the reference solution has. One that fails there
asks for more than the reference does: a requirement the task statement leaves open, or a defect the
reference shares. A probe that cannot run against the reference (it uses a name only the candidate
defines, it times out, or pytest cannot collect it) proves nothing either way.

    python3 -m bench.probes collect --work ~/klp-bench --out probes.json        # needs the recorded runs
    python3 -m bench.probes reference --work ~/klp-bench --pack probes.json     # needs only `prepare`

`collect` reads the runs a benchmark wrote under --work. `reference` repeats the reference half from a
published probes.json, so anyone with a prepared benchmark folder can check it without the runs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.features import ARMS, DATASET_REVISION, DATASET_URL, box, sh  # noqa: E402
from klp.snapshot import GIT_SAFE as GIT, Snapshots  # noqa: E402

PROBE_TIMEOUT = 180  # what the runner allows a probe
MISSING_NAME = re.compile(r"\b(?:ImportError|ModuleNotFoundError|NameError)\b|cannot import name|has no attribute"
                          r"|unexpected keyword argument")


def write_events(receipt: dict) -> list[tuple[str, int, str]]:
    """Every time a review wrote a file into /workspace/probes, in order: (file, review number, finding id).

    A review writes one file per probed finding, then its acceptance file, which all of its acceptance
    findings share. A later write to the same file name replaces the earlier content.
    """
    events = []
    for number, review in enumerate(receipt.get("reviews", []), 1):
        acceptance_written = False
        for finding in review["findings"]:
            if finding.get("carried") or not (finding.get("probe") or {}).get("file"):
                continue
            if finding.get("source") == "acceptance":
                if not acceptance_written:
                    events.append((finding["probe"]["file"], number, "acceptance"))
                    acceptance_written = True
            else:
                events.append((finding["probe"]["file"], number, finding["id"]))
    return events


def probed_findings(receipt: dict) -> list[dict]:
    """Each finding that ran a probe, with whether its probe file still holds the content it ran with."""
    events = write_events(receipt)
    owner = {file: (number, writer) for file, number, writer in events}  # the last write wins
    rows = []
    for number, review in enumerate(receipt.get("reviews", []), 1):
        for finding in review["findings"]:
            probe = finding.get("probe") or {}
            if finding.get("carried") or not probe.get("file"):
                continue
            writer = "acceptance" if finding.get("source") == "acceptance" else finding["id"]
            rows.append(dict(review=number, finding=finding, reviewed_revision=review["reviewed_revision"],
                             retained=owner.get(probe["file"]) == (number, writer)))
    return rows


def checkout(env_dir: Path, ws: Path, *, candidate: bytes | None = None, reference: Path | None = None) -> dict:
    """A pristine checkout of the task's commit with one patch applied, ready for a probe."""
    shutil.rmtree(ws, ignore_errors=True)
    ws.mkdir(parents=True)
    sh("cp", "-a", str(env_dir / "ws/repo"), str(ws / "repo"))
    steps = ["true"]
    if candidate:
        (ws / "candidate.patch").write_bytes(candidate)
        steps.append(f"{GIT} apply --binary --whitespace=nowarn /workspace/candidate.patch")
    if reference:
        shutil.copy(reference, ws / "feature.patch")
        steps.append("(git apply --ignore-whitespace --ignore-space-change /workspace/feature.patch "
                     "|| git apply --3way /workspace/feature.patch)")
    return box(ws, env_dir).run(" && ".join(steps), limit=1500)


def run_probe(env_dir: Path, ws: Path, file: str, content: str, command: str, **patch) -> dict:
    """Apply one patch to a pristine checkout, write the probe where the runner wrote it and run it."""
    try:
        setup = checkout(env_dir, ws, **patch)
        if setup["returncode"] != 0:
            return dict(stage="apply", returncode=None, timed_out=False, output=setup["output"][-600:])
        probes = ws / "probes"
        probes.mkdir()
        (probes / Path(file).name).write_text(content)
        done = box(ws, env_dir).run(command, timeout=PROBE_TIMEOUT, limit=3000)
        return dict(stage="probe", returncode=done["returncode"], timed_out=done["timed_out"], output=done["output"])
    finally:
        shutil.rmtree(ws, ignore_errors=True)


def first_reason(output: str) -> str:
    """The first error line pytest prints for a failed test, or its summary line."""
    error = re.search(r"^E\s+(.+)$", output, re.M)
    if error:
        return error.group(1).strip()[:200]
    summary = re.search(r"^(?:FAILED|ERROR) \S+(?: - (.+))?$", output, re.M)
    if summary and summary.group(1):
        return summary.group(1).strip()[:200]
    return output.strip().splitlines()[-1][:200] if output.strip() else ""


def outcome(result: dict, command: str) -> tuple[str, str]:
    """What a probe run on the reference solution shows: agrees, asks_more or inconclusive, and why."""
    if result["stage"] == "apply":
        return "inconclusive", "the reference solution did not apply"
    if result["timed_out"]:
        return "inconclusive", "timed out"
    if result["returncode"] == 0:
        return "agrees", ""
    if "pytest" in command and result["returncode"] != 1:
        return "inconclusive", f"pytest could not run the probe (exit {result['returncode']})"
    reason = first_reason(result["output"])
    found = MISSING_NAME.search(result["output"])
    if found:
        return "inconclusive", "uses a name the reference does not define: " + (reason or found.group(0))
    return "asks_more", reason


def reproduced(recorded: dict, rerun: dict) -> bool:
    """Whether a rerun on the candidate gave the outcome the runner recorded for the finding."""
    if rerun["stage"] != "probe":
        return False
    if recorded.get("timed_out") or rerun["timed_out"]:
        return bool(recorded.get("timed_out")) == bool(rerun["timed_out"])
    return recorded.get("returncode") == rerun["returncode"]


def review_arms(work: Path, arms: list[str] | None) -> list[str]:
    present = {p.name for p in (work / "runs").iterdir() if p.is_dir()}
    return [a for a in ARMS if ARMS[a][1] and a in present and (not arms or a in arms)]


def collect(work: Path, out: Path, arms: list[str] | None, ids: list[str] | None, jobs: int) -> dict:
    """Rerun every recorded probe on its reviewed candidate and on the reference solution."""
    tasks = {t["id"]: t for t in json.loads((work / "tasks.json").read_text())["tasks"] if t["valid"]}
    jobs_list = []
    for arm in review_arms(work, arms):
        for task_id in sorted(tasks):
            if ids and task_id not in ids:
                continue
            run_dir = work / "runs" / arm / task_id
            if not (run_dir / "receipt.json").exists():
                continue
            receipt = json.loads((run_dir / "receipt.json").read_text())
            grades = json.loads((run_dir / "result.json").read_text()).get("grades", {})
            for row in probed_findings(receipt):
                jobs_list.append((arm, task_id, run_dir, receipt, grades, row))
    print(f"{len(jobs_list)} probed findings in {len({(a, t) for a, t, *_ in jobs_list})} runs", flush=True)

    patches: dict[tuple, bytes] = {}

    def candidate_patch(arm: str, task: dict, run_dir: Path, receipt: dict, revision: str) -> bytes:
        key = (arm, task["id"], revision)
        if key not in patches:
            store = Snapshots(box(run_dir / "ws", work / "envs" / task["env"]), run_dir / "snapshots")
            patches[key] = store.patch(receipt["base_revision"], revision)
        return patches[key]

    def one(item) -> dict:
        arm, task_id, run_dir, receipt, grades, row = item
        task, finding = tasks[task_id], row["finding"]
        probe, env_dir = finding["probe"], work / "envs" / tasks[task_id]["env"]
        local = run_dir / "ws" / Path(probe["file"]).relative_to("/workspace")
        entry = dict(arm=arm, task=task_id, review=row["review"], id=finding["id"],
                     source=finding.get("source", "critic"), claim=finding["claim"],
                     disposition=finding["disposition"], reviewed_revision=row["reviewed_revision"],
                     candidate_passed_hidden_tests=bool(grades.get(row["reviewed_revision"], {}).get("passed")),
                     retained=row["retained"] and local.is_file(),
                     recorded=dict(returncode=probe.get("returncode"), timed_out=bool(probe.get("timed_out"))))
        if not entry["retained"]:
            return entry
        content = local.read_text()
        entry["probe"] = dict(file=Path(probe["file"]).name, command=probe["command"],
                              sha256=hashlib.sha256(content.encode()).hexdigest(), content=content)
        # Runners before 0.5 restarted finding ids in every review, so the review number keeps this unique.
        scratch = work / "scratch" / "probes" / arm / task_id / f"{row['review']}-{re.sub(r'[^A-Za-z0-9_.-]', '_', finding['id'])}"
        patch = candidate_patch(arm, task, run_dir, receipt, row["reviewed_revision"])
        again = run_probe(env_dir, scratch / "candidate", probe["file"], content, probe["command"], candidate=patch)
        entry["candidate"] = dict(returncode=again["returncode"], timed_out=again["timed_out"])
        entry["reproduced"] = reproduced(entry["recorded"], again)
        ref = run_probe(env_dir, scratch / "reference", probe["file"], content, probe["command"],
                        reference=Path(task["gold_patch"]))
        result, reason = outcome(ref, probe["command"])
        entry["reference"] = dict(returncode=ref["returncode"], timed_out=ref["timed_out"], outcome=result, reason=reason)
        return entry

    rows = []
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for n, entry in enumerate(pool.map(one, jobs_list), 1):
            rows.append(entry)
            if n % 50 == 0 or n == len(jobs_list):
                print(f"  {n}/{len(jobs_list)}", flush=True)
    shutil.rmtree(work / "scratch" / "probes", ignore_errors=True)
    pack = dict(dataset=DATASET_URL, revision=DATASET_REVISION, probe_timeout_seconds=PROBE_TIMEOUT,
                outcomes=dict(agrees="the probe passes on the reference solution",
                              asks_more="the probe fails on the reference solution too",
                              inconclusive="the probe cannot run against the reference solution"),
                findings=rows)
    out.write_text(json.dumps(pack, indent=1) + "\n")
    summarize(rows)
    print(f"-> {out}")
    return pack


def reference(work: Path, pack_file: Path, jobs: int) -> int:
    """Repeat the reference half of a published probes.json on a prepared benchmark folder."""
    tasks = {t["id"]: t for t in json.loads((work / "tasks.json").read_text())["tasks"] if t["valid"]}
    pack = json.loads(pack_file.read_text())
    rows = [r for r in pack["findings"] if r.get("probe")]

    def one(row: dict) -> tuple[dict, str]:
        task, probe = tasks[row["task"]], row["probe"]
        scratch = (work / "scratch" / "probes-reference" / row["arm"] / row["task"]
                   / f"{row['review']}-{re.sub(r'[^A-Za-z0-9_.-]', '_', row['id'])}")
        ref = run_probe(work / "envs" / task["env"], scratch, probe["file"], probe["content"], probe["command"],
                        reference=Path(task["gold_patch"]))
        return row, outcome(ref, probe["command"])[0]

    differ = 0
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        for row, got in pool.map(one, rows):
            if got != row["reference"]["outcome"]:
                differ += 1
                print(f"  {row['arm']}/{row['task']} {row['id']}: published {row['reference']['outcome']}, now {got}")
    shutil.rmtree(work / "scratch" / "probes-reference", ignore_errors=True)
    print(f"{len(rows) - differ} of {len(rows)} probes give the published outcome on the reference solution.")
    return 1 if differ else 0


def summarize(rows: list[dict]) -> None:
    print(f"\n{'arm':12s}{'probed':>8s}{'kept':>6s}{'reproduced':>12s}{'agrees':>8s}{'asks more':>11s}{'inconclusive':>14s}")
    for arm in dict.fromkeys(r["arm"] for r in rows):
        mine = [r for r in rows if r["arm"] == arm]
        kept = [r for r in mine if r["retained"]]
        same = [r for r in kept if r.get("reproduced")]
        confirmed = [r for r in same if r["disposition"] == "confirmed"]
        count = {k: sum(r["reference"]["outcome"] == k for r in confirmed) for k in ("agrees", "asks_more", "inconclusive")}
        print(f"{arm:12s}{len(mine):>8d}{len(kept):>6d}{len(same):>12d}{count['agrees']:>8d}{count['asks_more']:>11d}"
              f"{count['inconclusive']:>14d}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("collect", "reference"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="collect: where to write probes.json")
    parser.add_argument("--pack", type=Path, help="reference: a published probes.json")
    parser.add_argument("--arms", default="", help="collect: comma-separated review arms (default: all present)")
    parser.add_argument("--ids", default="", help="collect: comma-separated task ids")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    if args.command == "collect":
        if not args.out:
            parser.error("collect needs --out")
        collect(args.work, args.out, [a for a in args.arms.split(",") if a] or None,
                [i for i in args.ids.split(",") if i] or None, args.jobs)
    else:
        if not args.pack:
            parser.error("reference needs --pack")
        sys.exit(reference(args.work, args.pack, args.jobs))


if __name__ == "__main__":
    main()
