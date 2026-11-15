"""Re-run the critics' probes from a feature benchmark run against the dataset's reference solution.

A probe is the test a critic writes to back a finding: it fails on the candidate if the finding is real.
Each recorded probe whose file still holds the content it ran with runs twice in the sandbox, with no
network, using the command the runner recorded for it:

  1. on the candidate the critic reviewed, to show the rerun reproduces the recorded exit code;
  2. on the reference solution the dataset ships with the task.

A probe whose file was written again later (by a later review, or a later probe in the same review) cannot
be rerun; it is listed without reruns.

A probe that passes on the reference asks for behaviour the reference solution has. One that fails there
asks for more than the reference does: a requirement the task statement leaves open, or a defect the
reference shares. A probe that cannot run against the reference (its output names a missing import,
name, attribute or keyword, it times out, or pytest cannot collect it) proves nothing either way. The
missing-name test is a text match on the output, so it files a few probes in the wrong one of the last
two groups; it never moves a probe into or out of "agrees".

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
import os
import re
import shutil
import stat
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench.features import ARMS, DATASET_REVISION, DATASET_URL, box, sh  # noqa: E402
from klp.sandbox import identity_dir  # noqa: E402
from klp.snapshot import GIT_SAFE as GIT, Snapshots  # noqa: E402

PROBE_TIMEOUT = 180  # what the runner allows a probe
PROBE_MAX_BYTES = 1 << 20
MISSING_NAME = re.compile(r"\b(?:ImportError|ModuleNotFoundError|NameError)\b|cannot import name|has no attribute"
                          r"|unexpected keyword argument")
STAGING_FAILED = "could not write "  # how the runner records a probe file it could not write


def staged(probe: dict) -> bool:
    """False when the runner could not write the probe file, so the finding never ran its own content."""
    return not (probe.get("returncode") is None and str(probe.get("output") or "").startswith(STAGING_FAILED))


def write_events(receipt: dict) -> list[tuple[str, int, int | str | None]]:
    """Every write a review made into /workspace/probes, in order: (file, review number, writer).

    A review writes one file per probed finding, in the order of its findings, then its acceptance file,
    whether or not that file produced findings; its acceptance findings all share it. The writer is the
    finding's position in the review, "acceptance", or None for a write that failed: the old file may
    already be gone, and the finding never ran its own content. A later write to a file name replaces
    the earlier content.
    """
    events = []
    for number, review in enumerate(receipt.get("reviews", []), 1):
        acceptance = (review.get("acceptance") or {}).get("file")
        for position, finding in enumerate(review["findings"]):
            probe = finding.get("probe") or {}
            if finding.get("carried") or not probe.get("file"):
                continue
            if finding.get("source") == "acceptance":
                acceptance = acceptance or probe["file"]
                continue
            events.append((probe["file"], number, position if staged(probe) else None))
        if acceptance:
            events.append((acceptance, number, "acceptance"))
    return events


def probed_findings(receipt: dict) -> list[dict]:
    """Each finding that ran a probe, with whether its probe file still holds the content it ran with."""
    owner = {file: (number, writer) for file, number, writer in write_events(receipt)}  # the last write wins
    rows = []
    for number, review in enumerate(receipt.get("reviews", []), 1):
        for position, finding in enumerate(review["findings"]):
            probe = finding.get("probe") or {}
            if finding.get("carried") or not probe.get("file"):
                continue
            writer = "acceptance" if finding.get("source") == "acceptance" else position
            rows.append(dict(review=number, finding=finding, reviewed_revision=review["reviewed_revision"],
                             retained=owner.get(probe["file"]) == (number, writer)))
    return rows


def probe_name(file: str) -> str | None:
    """The probe's file name, if it is one the runner could have written; None for anything else."""
    name = Path(str(file)).name
    return name if re.fullmatch(r"[A-Za-z0-9_.-]{1,255}", name) and name not in (".", "..") else None


def read_probe(ws: Path, name: str) -> str | None:
    """The text of ws/probes/<name>, or None unless it is a small regular file reached without a link.

    The run's workspace was writable by the models' code, so a link planted there could name any file on
    the host. Each part of the path is opened on its own with O_NOFOLLOW; O_NONBLOCK keeps a planted FIFO
    from blocking the open.
    """
    if probe_name(name) != name:
        return None
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    fds: list[int] = []
    try:
        fds.append(os.open(ws, flags | os.O_DIRECTORY))
        fds.append(os.open("probes", flags | os.O_DIRECTORY, dir_fd=fds[-1]))
        fds.append(os.open(name, flags | os.O_NONBLOCK, dir_fd=fds[-1]))
        info = os.fstat(fds[-1])
        if not stat.S_ISREG(info.st_mode) or info.st_size > PROBE_MAX_BYTES:
            return None
        with open(fds[-1], "rb", closefd=False) as f:
            data = f.read(PROBE_MAX_BYTES + 1)
        return None if len(data) > PROBE_MAX_BYTES else data.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    finally:
        for fd in fds:
            os.close(fd)


def scratch_root(work: Path, kind: str) -> Path:
    """A scratch folder of this invocation's own under --work/scratch, so concurrent runs never share one."""
    base = work / "scratch"
    base.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=f"{kind}-", dir=base)).resolve()


def scratch_dir(root: Path, index: int) -> Path:
    """The numbered folder for one probe under an invocation's scratch root. Never built from recorded text."""
    root = root.resolve()
    path = (root / str(int(index))).resolve()
    if path.parent != root:
        raise ValueError(f"scratch folder {path} is outside {root}")
    return path


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
        name = probe_name(file)
        if name is None:
            return dict(stage="apply", returncode=None, timed_out=False, output=f"unsafe probe file name: {file!r}")
        probes = ws / "probes"
        probes.mkdir()
        (probes / name).write_text(content)
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
    """Rerun every recorded probe whose file was not written again later, on its reviewed candidate
    and on the reference solution. Overwritten probes are listed without reruns."""
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

    def one(numbered) -> dict:
        index, (arm, task_id, run_dir, receipt, grades, row) = numbered
        task, finding = tasks[task_id], row["finding"]
        probe, env_dir = finding["probe"], work / "envs" / tasks[task_id]["env"]
        name = probe_name(probe["file"])
        content = read_probe(run_dir / "ws", name) if name and row["retained"] else None
        entry = dict(arm=arm, task=task_id, review=row["review"], id=finding["id"],
                     source=finding.get("source", "critic"), claim=finding["claim"],
                     disposition=finding["disposition"], reviewed_revision=row["reviewed_revision"],
                     candidate_passed_hidden_tests=bool(grades.get(row["reviewed_revision"], {}).get("passed")),
                     retained=content is not None,
                     recorded=dict(returncode=probe.get("returncode"), timed_out=bool(probe.get("timed_out"))))
        if content is None:
            return entry
        entry["probe"] = dict(file=name, command=probe["command"],
                              sha256=hashlib.sha256(content.encode()).hexdigest(), content=content)
        scratch = scratch_dir(root, index)
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
    identity_dir()  # the sandbox's passwd and group, made once before the threads start
    root = scratch_root(work, "probes")
    try:
        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            for n, entry in enumerate(pool.map(one, enumerate(jobs_list)), 1):
                rows.append(entry)
                if n % 50 == 0 or n == len(jobs_list):
                    print(f"  {n}/{len(jobs_list)}", flush=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
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
    findings = pack.get("findings") if isinstance(pack, dict) else None
    rows = [r for r in findings if isinstance(r, dict) and r.get("probe")] if isinstance(findings, list) else []
    if not rows:
        raise SystemExit(f"{pack_file} lists no probes to rerun")
    unknown = [r for r in rows if r.get("task") not in tasks]
    if unknown:
        raise SystemExit(f"{len(unknown)} probes name tasks this benchmark folder does not have")
    malformed = [r for r in rows if not isinstance(r["probe"], dict) or not isinstance(r.get("reference"), dict)
                 or not all(isinstance(r["probe"].get(k), str) for k in ("file", "content", "command"))]
    if malformed:
        raise SystemExit(f"{len(malformed)} probes lack a file name, content, command or published outcome")

    def one(numbered) -> tuple[dict, str]:
        index, row = numbered
        task, probe = tasks[row["task"]], row["probe"]
        ref = run_probe(work / "envs" / task["env"], scratch_dir(root, index), probe["file"],
                        probe["content"], probe["command"], reference=Path(task["gold_patch"]))
        return row, outcome(ref, probe["command"])[0]

    differ = 0
    identity_dir()  # the sandbox's passwd and group, made once before the threads start
    root = scratch_root(work, "probes-reference")
    try:
        with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
            for row, got in pool.map(one, enumerate(rows)):
                if got != row["reference"].get("outcome"):
                    differ += 1
                    print(f"  {row.get('arm')}/{row['task']} {row.get('id')}: published "
                          f"{row['reference'].get('outcome')}, now {got}")
    finally:
        shutil.rmtree(root, ignore_errors=True)
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
