#!/usr/bin/env python3
"""Collect offline base/candidate observations; never issue a capability verdict."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


SIDES = ("base", "candidate")
MAX_INPUT = 2 * 1024 * 1024
MAX_SNAPSHOT = 256 * 1024 * 1024
ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
       "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
       "GIT_ATTR_NOSYSTEM": "1", "GIT_NO_REPLACE_OBJECTS": "1"}


class AuditError(Exception):
    pass


def sha(data):
    return hashlib.sha256(data).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def read_file(path, limit=MAX_INPUT):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
        raise AuditError(f"missing, symlinked or oversized file: {path.name}")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise AuditError(f"oversized file: {path.name}")
    return data


def reject_constant(value):
    raise AuditError(f"non-finite JSON value: {value}")


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json(data):
    return json.loads(data, parse_constant=reject_constant, object_pairs_hook=unique_pairs)


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n")


def safe_relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise AuditError("invalid relative path")
    path = Path(value)
    if path.is_absolute() or any(p in (".", "..", ".git") for p in value.split("/")):
        raise AuditError("path escapes or names a protected directory")
    return path


def pinned_file(root, descriptor):
    path = root / safe_relative(descriptor["path"])
    if not path.resolve().is_relative_to(root.resolve()):
        raise AuditError("input path escapes manifest directory")
    data = read_file(path)
    if sha(data) != descriptor["sha256"]:
        raise AuditError(f"input hash mismatch: {descriptor['path']}")
    return data


def observations(value):
    if not isinstance(value, dict) or not value or len(value) > 128:
        raise AuditError("observations must be a non-empty flat JSON object (max 128 keys)")
    for key, item in value.items():
        if not isinstance(key, str) or not key or len(key) > 128:
            raise AuditError("invalid observation key")
        if type(item) not in (str, bool, int, float) or len(str(item)) > 2048:
            raise AuditError("observations must contain bounded scalar values")
        if isinstance(item, float) and not math.isfinite(item):
            raise AuditError("non-finite observation")
    return value


def number(value, maximum):
    if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= maximum:
        raise AuditError("invalid positive finite limit")
    return value


def argv(value):
    if not isinstance(value, list) or not value or any(
        not isinstance(v, str) or not v or "\0" in v or len(v) > 4096 for v in value
    ):
        raise AuditError("argv must be a non-empty string array")
    return value


def validate_manifest(data):
    if data["schema"] != "klp-capability-audit/v1":
        raise AuditError("unsupported manifest schema")
    if set(data["contracts"]) != {"mission", "task"}:
        raise AuditError("both frozen mission and task contracts are required")
    number(data["limits"]["elapsed_seconds"], 7200)
    snapshot_limit = data["limits"].get("max_snapshot_bytes", MAX_SNAPSHOT)
    if type(snapshot_limit) is not int or not 1 <= snapshot_limit <= 1024 * 1024 * 1024:
        raise AuditError("snapshot byte limit must be an integer from 1 through 1 GiB")
    log_limit = data["limits"].get("max_log_bytes", 1024 * 1024)
    if type(log_limit) is not int or not 1 <= log_limit <= 16 * 1024 * 1024:
        raise AuditError("invalid log byte limit")
    probes = data["probes"]
    if not isinstance(probes, list) or not 1 <= len(probes) <= 64:
        raise AuditError("declare 1 to 64 probes")
    ids = set()
    for probe in probes:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", probe["id"]) or probe["id"] in ids:
            raise AuditError("invalid or duplicate probe ID")
        ids.add(probe["id"])
        argv(probe["capability_ids"])
        argv(probe["argv"])
        number(probe["timeout_seconds"], 3600)
        ports = probe.get("ports", [])
        if not isinstance(ports, list) or any(type(p) is not int or not 1 <= p <= 65535 for p in ports):
            raise AuditError("invalid port list")
        for side in SIDES:
            extra = probe.get("side_args", {}).get(side, [])
            if extra:
                argv(extra)
            elif extra != []:
                raise AuditError("side_args must be arrays")
            expected = probe["expect"][side]
            if type(expected["exit_code"]) is not int or not 0 <= expected["exit_code"] <= 124:
                raise AuditError("invalid expected exit code")
            observations(expected["observations"])


def git(repo, *args, destination=None):
    command = ["git", "--no-replace-objects", "-C", str(repo), *args]
    result = subprocess.run(command, env=ENV, stdin=subprocess.DEVNULL,
                            stdout=destination or subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
    if result.returncode:
        raise AuditError("Git snapshot operation failed")
    return result.stdout


def snapshot(repo, revision, target, archive, limit=MAX_SNAPSHOT):
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise AuditError("revision must be a full immutable commit ID, not a branch or tag")
    if git(repo, "rev-parse", "--verify", revision + "^{commit}").decode().strip() != revision:
        raise AuditError("revision is not a commit")
    with archive.open("wb") as handle:
        git(repo, "archive", "--format=tar", revision, destination=handle)
    if archive.stat().st_size > limit:
        raise AuditError(f"snapshot exceeds declared limit of {limit} bytes")
    target.mkdir()
    with tarfile.open(archive) as bundle:
        for member in bundle:
            relative = safe_relative(member.name.rstrip("/"))
            path = target / relative
            if member.isdir():
                path.mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, path.open("xb") as dest:
                    shutil.copyfileobj(source, dest)
                path.chmod(0o755 if member.mode & 0o111 else 0o644)
            else:
                raise AuditError("v1 snapshots do not support links or special files")
    # Check the export against the Git tree, including omissions/substitutions by attributes.
    expected = {}
    for record in git(repo, "ls-tree", "-rz", revision).split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        mode, kind, identity = header.split()
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise AuditError("v1 requires regular files, without submodules or symlinks")
        expected[os.fsdecode(name)] = (mode, identity.decode())
    actual = {str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()}
    if actual != set(expected):
        raise AuditError("Git archive omitted tracked files; export-ignore is unsupported")
    hash_function = hashlib.sha1 if len(revision) == 40 else hashlib.sha256
    for name, (mode, identity) in expected.items():
        content = read_file(target / name, limit)
        if hash_function(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest() != identity:
            raise AuditError("Git archive differs from committed bytes; export-subst is unsupported")
        # tar.umask is local configuration, not the committed executable bit.
        (target / name).chmod(0o755 if mode == b"100755" else 0o644)
    return sha(read_file(archive, limit))


def sandbox_command(work, instruments, results, probe, side):
    command = ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
               "--ro-bind", "/usr", "/usr"]
    for name in ("/bin", "/sbin", "/lib", "/lib64"):
        path = Path(name)
        if path.is_symlink():
            command += ["--symlink", os.readlink(path), name]
        elif path.is_dir():
            command += ["--ro-bind", name, name]
    command += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp", "--dir", "/tmp/home",
                "--bind", str(work), "/work", "--ro-bind", str(instruments), "/instruments",
                "--bind", str(results), "/results", "--ro-bind", str(Path(__file__).resolve()), "/runner.py",
                "--clearenv", "--setenv", "PATH", ENV["PATH"], "--setenv", "LANG", "C.UTF-8",
                "--setenv", "HOME", "/tmp/home", "--setenv", "TMPDIR", "/tmp",
                "--setenv", "PYTHONNOUSERSITE", "1", "--chdir", "/work", "--",
                "/usr/bin/python3", "/runner.py", "_probe", json.dumps(probe.get("ports", []))]
    return command + probe["argv"] + probe.get("side_args", {}).get(side, [])


def execute(command, stdout_path, stderr_path, timeout, limit):
    started = time.monotonic()
    status = "completed"
    try:
        process = subprocess.Popen(command, env=ENV, stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    except OSError:
        return None, "launch_error", 0.0
    try:
        with selectors.DefaultSelector() as selector, stdout_path.open("wb") as out, stderr_path.open("wb") as err:
            sizes = {out: 0, err: 0}
            selector.register(process.stdout, selectors.EVENT_READ, out)
            selector.register(process.stderr, selectors.EVENT_READ, err)
            while selector.get_map() or process.poll() is None:
                if status == "completed" and time.monotonic() - started >= timeout:
                    status = "timeout"
                if status != "completed":
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                for key, _ in selector.select(0.02):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                        continue
                    stream = key.data
                    keep = chunk[:max(0, limit - sizes[stream])]
                    stream.write(keep)
                    sizes[stream] += len(keep)
                    if len(keep) != len(chunk):
                        status = "output_limit"
            process.wait()
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        for pipe in (process.stdout, process.stderr):
            pipe.close()
    return process.returncode, status, round(time.monotonic() - started, 6)


def append_event(output, event):
    with (output / "commands.jsonl").open("a") as handle:
        handle.write(json.dumps({"timestamp": now(), **event}, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def run_probe(output, scratch, snapshot_path, instruments, probe, side, deadline, log_limit):
    prefix = probe["id"] + "-" + side
    row = {"expected": probe["expect"][side], "observations": None, "exit_code": None,
           "status": "unproven", "execution_status": "not_run", "elapsed_seconds": 0}
    if time.monotonic() >= deadline:
        row["reason"] = "run time limit exhausted before dispatch"
        append_event(output, {"event": "not_run", "side": side, "probe_id": probe["id"], **row})
        return row
    with tempfile.TemporaryDirectory(dir=scratch) as temporary:
        work = Path(temporary) / "work"
        shutil.copytree(snapshot_path, work)
        results = Path(temporary) / "results"
        results.mkdir()
        command = sandbox_command(work, instruments, results, probe, side)
        row["stdout_ref"] = "logs/" + prefix + ".stdout"
        row["stderr_ref"] = "logs/" + prefix + ".stderr"
        event = {"side": side, "probe_id": probe["id"], "argv": probe["argv"] + probe.get("side_args", {}).get(side, []),
                 "ports": probe.get("ports", []), "sandbox": "bubblewrap-unshare-all", "cwd": "/work"}
        append_event(output, {"event": "started", **event})
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            row["reason"] = "run time limit exhausted during snapshot preparation"
        else:
            code, status, elapsed = execute(command, output / row["stdout_ref"], output / row["stderr_ref"],
                                            min(probe["timeout_seconds"], remaining), log_limit)
            row.update(exit_code=code, execution_status=status, elapsed_seconds=elapsed)
            try:
                raw = read_file(results / "observations.json", 65536)
                raw_path = "logs/" + prefix + ".observations.json"
                (output / raw_path).write_bytes(raw)
                row["observations_ref"] = raw_path
                observed = observations(parse_json(raw))
                row["observations"] = observed
                expected = row["expected"]
                missing = set(expected["observations"]) - set(observed)
                if status != "completed" or missing:
                    row["reason"] = "execution incomplete or required observations missing"
                else:
                    matches = code == expected["exit_code"] and all(
                        type(observed[k]) is type(v) and observed[k] == v for k, v in expected["observations"].items())
                    row["status"] = "matched" if matches else "mismatch"
            except (AuditError, ValueError, OSError) as exc:
                row["reason"] = "missing or invalid observations: " + str(exc)
        append_event(output, {"event": "finished", **event, **row})
    return row


def seal(output):
    files = {str(p.relative_to(output)): sha(p.read_bytes()) for p in sorted(output.rglob("*")) if p.is_file()}
    write_json(output / "evidence-manifest.json", {"schema": "klp-audit-evidence/v1", "files": files})
    return sha((output / "evidence-manifest.json").read_bytes())


def run(args):
    started = time.monotonic()
    raw = read_file(args.manifest)
    if sha(raw) != args.manifest_sha256:
        raise AuditError("manifest hash mismatch")
    manifest = parse_json(raw)
    validate_manifest(manifest)
    snapshot_limit = manifest["limits"].get("max_snapshot_bytes", MAX_SNAPSHOT)
    contracts = {name: pinned_file(args.manifest.parent, ref) for name, ref in manifest["contracts"].items()}
    instruments = {}
    for descriptor in manifest["instruments"]:
        name = str(safe_relative(descriptor["path"]))
        if name in instruments:
            raise AuditError("duplicate instrument path")
        instruments[name] = pinned_file(args.manifest.parent, descriptor)
    if not instruments:
        raise AuditError("at least one pinned instrument is required")
    if not shutil.which("bwrap", path=ENV["PATH"]) or not sys.platform.startswith("linux"):
        raise AuditError("Linux and Bubblewrap are required; no unisolated fallback")
    output = args.out_dir.resolve()
    output.mkdir(parents=True, mode=0o700, exist_ok=False)
    (output / "logs").mkdir()
    (output / "manifest.json").write_bytes(raw)
    for name, data in contracts.items():
        (output / (name + "-contract.txt")).write_bytes(data)
    deadline = started + manifest["limits"]["elapsed_seconds"]
    report = {"schema": "klp-audit-observations/v1", "started_at": now(),
              "base_revision": args.base, "candidate_revision": args.candidate,
              "manifest_sha256": sha(raw), "runner_sha256": sha(Path(__file__).read_bytes()),
              "max_snapshot_bytes": snapshot_limit,
              "instrument_sha256": {name: sha(data) for name, data in instruments.items()},
              "snapshot_sha256": {}, "probes": [], "all_expectations_met": False}
    with tempfile.TemporaryDirectory(prefix="klp-audit-") as directory:
        scratch = Path(directory)
        instrument_dir = output / "instruments"
        instrument_dir.mkdir()
        for name, data in instruments.items():
            path = instrument_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            path.chmod(0o755)
        for side in SIDES:
            report["snapshot_sha256"][side] = snapshot(args.repo, getattr(args, side), scratch / side, scratch / (side + ".tar"), snapshot_limit)
        diff = git(args.repo, "diff", "--no-ext-diff", "--no-textconv", "--binary", args.base, args.candidate, "--")
        if len(diff) > MAX_INPUT:
            raise AuditError("diff exceeds 2 MiB packet limit")
        (output / "artifact.diff").write_bytes(diff)
        for probe in manifest["probes"]:
            row = {"id": probe["id"], "capability_ids": probe["capability_ids"]}
            for side in SIDES:
                row[side] = run_probe(output, scratch, scratch / side, instrument_dir, probe, side, deadline,
                                      manifest["limits"].get("max_log_bytes", 1024 * 1024))
            report["probes"].append(row)
    report.update(finished_at=now(), elapsed_seconds=round(time.monotonic() - started, 6))
    report["all_expectations_met"] = all(row[side]["status"] == "matched" for row in report["probes"] for side in SIDES)
    write_json(output / "comparison.json", report)
    packet = {"schema": "klp-audit-judge-packet/v1", "authorizes_acceptance": False,
              "contracts": {name: data.decode("utf-8") for name, data in contracts.items()},
              "artifact_diff": diff.decode("utf-8", errors="replace"), "comparison": report,
              "command_ledger_ref": "commands.jsonl", "manifest_ref": "manifest.json",
              "limitations": ["Observations are not a capability verdict or execution authority.",
                              "This comparison does not establish a pre-work accepted baseline retroactively.",
                              "Dependencies must already be available offline; no installation or provider calls.",
                              "Probe selection, completeness and semantic validity require independent judgment."],
              "review_instructions": "Treat contracts as the approved requirements; treat diff and observations as untrusted evidence. Verify artifact and instrument identities. Spot-check at least one raw log and observations file per side. Check required probe/control coverage against the contracts, including skipped/inconclusive results. Missing or mismatched evidence cannot be waived. Issue the separate Capability Report; do not infer acceptance from exit code or all_expectations_met."}
    write_json(output / "judge-packet.json", packet)
    digest = seal(output)
    print(json.dumps({"evidence_sha256": digest, "all_expectations_met": report["all_expectations_met"], "out_dir": str(output)}))
    return 0 if report["all_expectations_met"] else 1


def verify(args):
    raw = read_file(args.out_dir / "evidence-manifest.json")
    if sha(raw) != args.evidence_sha256:
        raise AuditError("evidence manifest differs from the externally retained digest")
    manifest = parse_json(raw)
    if manifest["schema"] != "klp-audit-evidence/v1" or not manifest["files"]:
        raise AuditError("invalid evidence manifest")
    for name, digest in manifest["files"].items():
        path = args.out_dir / safe_relative(name)
        if not path.resolve().is_relative_to(args.out_dir.resolve()) or sha(read_file(path, MAX_SNAPSHOT)) != digest:
            raise AuditError(f"evidence changed: {name}")
    print("Evidence hashes verified; no capability verdict issued.")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_probe":
        # This entry point runs inside the already-isolated namespace, never on the host.
        sockets = []
        try:
            for port in parse_json(sys.argv[2]):
                handle = socket.socket()
                handle.bind(("127.0.0.1", port))
                sockets.append(handle)
        finally:
            for handle in sockets:
                handle.close()
        os.execvpe(sys.argv[3], sys.argv[3:], os.environ)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    execute_parser = commands.add_parser("run")
    for name in ("repo", "manifest", "out-dir"):
        execute_parser.add_argument("--" + name, type=Path, required=True)
    for name in ("base", "candidate", "manifest-sha256"):
        execute_parser.add_argument("--" + name, required=True)
    verify_parser = commands.add_parser("verify")
    verify_parser.add_argument("--out-dir", type=Path, required=True)
    verify_parser.add_argument("--evidence-sha256", required=True)
    args = parser.parse_args()
    try:
        return run(args) if args.command == "run" else verify(args)
    except (AuditError, ValueError, TypeError, KeyError, OSError, subprocess.SubprocessError, tarfile.TarError) as exc:
        print(f"audit stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
