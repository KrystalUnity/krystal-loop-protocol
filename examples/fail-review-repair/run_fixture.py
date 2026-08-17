#!/usr/bin/env python3
"""Run one offline, reproducible KLP fail-review-repair lifecycle."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CRITIC_SCRIPT = ROOT / "examples" / "openai-compatible-critic" / "critic.py"
VERDICT_SCHEMA = (
    ROOT / "examples" / "openai-compatible-critic" / "verdict.schema.json"
)
CRITIC_FAMILY = "fixture-critic"
CRITIC_MODEL = "fixture-critic-v1"
WORKER_FAMILY = "fixture-worker"


class FixtureError(Exception):
    """A bounded fixture setup or execution failure."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repair-round-limit", type=int, default=1)
    return parser.parse_args()


def canonical_json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


def digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(path)


def prepare_output(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise FixtureError("output path exists and is not a directory")
        if any(path.iterdir()):
            raise FixtureError("output directory must be empty")
        return
    path.mkdir(parents=True)


def run_command(
    command: list[str], *, cwd: Path, check: bool = True
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
    )
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise FixtureError(f"command failed ({' '.join(command)}): {detail}")
    return result


def git(workspace: Path, *arguments: str) -> str:
    return run_command(["git", *arguments], cwd=workspace).stdout.strip()


def commit(workspace: Path, message: str) -> str:
    git(workspace, "add", "--all")
    git(workspace, "commit", "-q", "-m", message)
    return git(workspace, "rev-parse", "HEAD")


def source_lines_changed(workspace: Path, base: str, result: str) -> int:
    output = git(workspace, "diff", "--numstat", base, result, "--", "score.py")
    total = 0
    for line in output.splitlines():
        added, deleted, _ = line.split("\t", 2)
        if added.isdigit() and deleted.isdigit():
            total += int(added) + int(deleted)
    return total


def run_score_check(workspace: Path, evidence_path: Path) -> bool:
    result = run_command(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
        cwd=workspace,
        check=False,
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(result.stdout + result.stderr, encoding="utf-8")
    return result.returncode == 0


class StateLedger:
    def __init__(self, path: Path, contract_revision: int) -> None:
        self.path = path
        self.contract_revision = contract_revision
        self.sequence = 0
        self.state: str | None = None
        self.tail_hash: str | None = None

    def append(
        self,
        new_state: str,
        *,
        actor: str,
        reason: str,
        artifact_revision: str | None,
    ) -> None:
        self.sequence += 1
        event = {
            "sequence": self.sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "previous_state": self.state,
            "new_state": new_state,
            "reason": reason,
            "actor": actor,
            "artifact_revision": artifact_revision,
            "contract_revision": self.contract_revision,
            "previous_event_hash": self.tail_hash,
        }
        event_hash = digest(event)
        event["event_hash"] = event_hash
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        self.state = new_state
        self.tail_hash = event_hash


class FakeCriticProvider:
    def __init__(self, verdict: dict[str, object]) -> None:
        self.verdict = verdict
        self.request_count = 0
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> "FakeCriticProvider":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib callback
                length = int(self.headers.get("Content-Length", "0"))
                self.rfile.read(length)
                owner.request_count += 1
                response = {
                    "id": "fixture-response",
                    "model": CRITIC_MODEL,
                    "usage": {"total_tokens": 0},
                    "choices": [
                        {"message": {"content": json.dumps(owner.verdict)}}
                    ],
                }
                payload = json.dumps(response).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise FixtureError("fake critic provider has not started")
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *args: object) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


def provider_verdict(
    revision: str,
    *,
    verdict: str,
    summary: str,
    findings: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "reviewed_revision": revision,
        "critic_provider_family": CRITIC_FAMILY,
        "critic_model": CRITIC_MODEL,
        "verdict": verdict,
        "summary": summary,
        "findings": findings,
        "limitations": ["Synthetic critic response; no model-quality claim."],
    }


def review_packet(
    *,
    contract_identity: dict[str, object],
    base_revision: str,
    result_revision: str,
    artifact_diff: str,
    check_status: str,
    evidence_id: str,
    evidence_content: str,
    unresolved_findings: list[str],
) -> dict[str, object]:
    return {
        "protocol": "klp-core/v0.2",
        "task_id": "klp-fixture-clamp-score",
        "contract_id": contract_identity["contract_id"],
        "contract_revision": contract_identity["revision"],
        "contract_hash": contract_identity["contract_hash"],
        "objective": "Clamp every integer score to the inclusive range 0..100.",
        "commitments": [
            {"id": "C1", "text": "Negative scores return 0."},
            {"id": "C2", "text": "Scores above 100 return 100."},
        ],
        "worker_provider_family": WORKER_FAMILY,
        "base_revision": base_revision,
        "result_revision": result_revision,
        "changed_files": ["score.py"],
        "artifact_diff": artifact_diff,
        "checks": [
            {
                "name": "score-unit-tests",
                "command": "python3 -m unittest discover -s tests -v",
                "status": check_status,
                "evidence_ref": evidence_id,
            }
        ],
        "evidence": [
            {"id": evidence_id, "kind": "test-output", "content": evidence_content}
        ],
        "known_limitations": ["Scripted worker and loopback fake critic."],
        "unresolved_findings": unresolved_findings,
    }


def run_critic(
    output: Path,
    *,
    round_number: int,
    packet: dict[str, object],
    verdict: dict[str, object],
) -> dict[str, Any]:
    packet_path = output / f"review-packet-round-{round_number}.json"
    critic_output = output / f"critic-round-{round_number}"
    write_json(packet_path, packet)
    with FakeCriticProvider(verdict) as provider:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
            "CRITIC_BASE_URL": provider.base_url,
            "CRITIC_API_KEY": "fixture-only-key",
            "CRITIC_MODEL": CRITIC_MODEL,
            "CRITIC_PROVIDER_FAMILY": CRITIC_FAMILY,
        }
        result = subprocess.run(
            [
                sys.executable,
                str(CRITIC_SCRIPT),
                "--packet",
                str(packet_path),
                "--schema",
                str(VERDICT_SCHEMA),
                "--out-dir",
                str(critic_output),
                "--timeout-seconds",
                "2",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            raise FixtureError(f"critic round {round_number} failed: {result.stderr}")
        if provider.request_count != 1:
            raise FixtureError("critic fixture expected exactly one loopback request")
    value = json.loads((critic_output / "verdict.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FixtureError("critic verdict artifact must be an object")
    return value


def setup_workspace(workspace: Path) -> str:
    workspace.mkdir()
    git(workspace, "init", "-q", "--initial-branch=main")
    git(workspace, "config", "user.name", "KLP Fixture")
    git(workspace, "config", "user.email", "fixture@example.invalid")
    (workspace / "tests").mkdir()
    (workspace / "score.py").write_text(
        "def clamp_score(value: int) -> int:\n"
        "    raise NotImplementedError\n",
        encoding="utf-8",
    )
    (workspace / "tests" / "test_score.py").write_text(
        "import unittest\n\n"
        "from score import clamp_score\n\n\n"
        "class ClampScoreTests(unittest.TestCase):\n"
        "    def test_negative_score_returns_zero(self) -> None:\n"
        "        self.assertEqual(0, clamp_score(-7))\n\n"
        "    def test_score_above_one_hundred_returns_one_hundred(self) -> None:\n"
        "        self.assertEqual(100, clamp_score(140))\n\n\n"
        "if __name__ == '__main__':\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    return commit(workspace, "fixture: establish frozen task base")


def build_contract(base_revision: str, repair_round_limit: int) -> dict[str, object]:
    return {
        "protocol": "klp-core/v0.2",
        "task_id": "klp-fixture-clamp-score",
        "objective": "Clamp every integer score to the inclusive range 0..100.",
        "base_revision": base_revision,
        "acceptance_criteria": [
            "Negative scores return 0.",
            "Scores above 100 return 100.",
            "The integrated artifact passes the declared unit tests.",
        ],
        "allowed_paths": ["score.py", "integration-manifest.json"],
        "protected_paths": ["tests/test_score.py"],
        "limits": {
            "repair_rounds": repair_round_limit,
            "elapsed_seconds": 60,
            "external_cost_usd": 0,
            "source_lines_changed": 8,
        },
        "delegation": {
            "coordinator_may": [
                "run declared checks",
                "adjudicate critic findings using declared evidence",
                "apply a repair within the frozen objective and allowed paths",
                "invalidate evidence made stale by a new artifact revision",
            ],
            "must_escalate": [
                "change the objective or acceptance criteria",
                "change allowed or protected paths",
                "increase a declared limit",
                "perform a live or irreversible action",
            ],
        },
    }


def final_receipt(
    *,
    status: str,
    contract_identity: dict[str, object],
    result_revision: str,
    integration_revision: str | None,
    source_line_count: int,
    repair_rounds_used: int,
    elapsed_seconds: float,
    ledger: StateLedger,
    unresolved_findings: list[str],
    human_decisions_required: list[str],
) -> dict[str, object]:
    return {
        "protocol": "klp-core/v0.2",
        "task_id": "klp-fixture-clamp-score",
        "status": status,
        "contract_identity": contract_identity,
        "result_revision": result_revision,
        "integration_revision": integration_revision,
        "claims": [
            "The recorded worker defect was checked before criticism.",
            "Every critic finding received an evidence-backed disposition.",
        ],
        "evidence_refs": [
            "evidence/worker-check.txt",
            "finding-dispositions.json",
            "critic-round-1/verdict.json",
        ],
        "measured_budget": {
            "repair_rounds_used": repair_rounds_used,
            "external_cost_usd": 0,
            "elapsed_seconds": elapsed_seconds,
            "source_lines_changed": source_line_count,
        },
        "limitations": [
            "The worker is scripted and the critic is a loopback fake provider.",
            "The fixture proves protocol mechanics, not model quality or production safety.",
        ],
        "unresolved_findings": unresolved_findings,
        "human_decisions_required": human_decisions_required,
        "state_ledger_tail_hash": ledger.tail_hash,
    }


def execute(output: Path, repair_round_limit: int) -> int:
    if repair_round_limit < 0:
        raise FixtureError("repair-round limit must be zero or greater")
    started_at = time.monotonic()
    prepare_output(output)
    workspace = output / "workspace"
    base_revision = setup_workspace(workspace)
    contract = build_contract(base_revision, repair_round_limit)
    contract_identity: dict[str, object] = {
        "contract_id": "klp-fixture-clamp-score",
        "revision": 1,
        "parent_contract_hash": None,
        "canonicalization": "json-sorted-compact-utf8",
        "contract_hash": digest(contract),
    }
    write_json(
        output / "contract.snapshot.json",
        {"identity": contract_identity, "contract": contract},
    )

    ledger = StateLedger(output / "state-events.jsonl", contract_revision=1)
    ledger.append(
        "draft",
        actor="fixture-author",
        reason="Created the bounded synthetic task contract.",
        artifact_revision=base_revision,
    )
    ledger.append(
        "authorized",
        actor="standing-policy",
        reason="Authorized offline execution with no live or paid action.",
        artifact_revision=base_revision,
    )
    ledger.append(
        "assigned",
        actor="coordinator",
        reason="Assigned score.py within the frozen contract.",
        artifact_revision=base_revision,
    )
    ledger.append(
        "building",
        actor="fixture-worker",
        reason="Started the scripted worker change.",
        artifact_revision=base_revision,
    )

    (workspace / "score.py").write_text(
        "def clamp_score(value: int) -> int:\n"
        "    return min(value, 100)\n",
        encoding="utf-8",
    )
    worker_revision = commit(workspace, "fixture: produce incomplete worker result")
    worker_evidence = output / "evidence" / "worker-check.txt"
    if run_score_check(workspace, worker_evidence):
        raise FixtureError("the intentional worker defect unexpectedly passed")
    ledger.append(
        "mechanical_check",
        actor="verifier",
        reason="Declared unit tests failed on the worker revision.",
        artifact_revision=worker_revision,
    )
    ledger.append(
        "critic_review",
        actor="coordinator",
        reason="Sealed the failed check and exact worker revision for review.",
        artifact_revision=worker_revision,
    )

    round_one_packet = review_packet(
        contract_identity=contract_identity,
        base_revision=base_revision,
        result_revision=worker_revision,
        artifact_diff=git(workspace, "diff", base_revision, worker_revision),
        check_status="failed",
        evidence_id="E1",
        evidence_content=worker_evidence.read_text(encoding="utf-8"),
        unresolved_findings=[],
    )
    round_one_findings = [
        {
            "finding_id": "F1",
            "severity": "important",
            "blocking": True,
            "commitment": "C1",
            "observed": "Negative scores are returned unchanged.",
            "expected": "Negative scores return 0.",
            "evidence_refs": ["E1"],
            "repair_acceptance": "The negative-score unit test passes.",
        },
        {
            "finding_id": "F2",
            "severity": "important",
            "blocking": True,
            "commitment": "C2",
            "observed": "The upper bound is not proven.",
            "expected": "Scores above 100 return 100.",
            "evidence_refs": ["E1"],
            "repair_acceptance": "The upper-bound unit test passes.",
        },
    ]
    first_verdict = run_critic(
        output,
        round_number=1,
        packet=round_one_packet,
        verdict=provider_verdict(
            worker_revision,
            verdict="NEEDS_FIXES",
            summary="One real defect and one unproven critic claim require adjudication.",
            findings=round_one_findings,
        ),
    )
    if first_verdict.get("verdict") != "NEEDS_FIXES":
        raise FixtureError("round-one critic did not return NEEDS_FIXES")

    dispositions = [
        {
            "finding_id": "F1",
            "status": "confirmed",
            "rationale": "The negative-score test failed on the reviewed revision.",
            "evidence_refs": ["evidence/worker-check.txt"],
            "artifact_revision": worker_revision,
        },
        {
            "finding_id": "F2",
            "status": "refuted",
            "rationale": "The upper-bound test passed on the reviewed revision.",
            "evidence_refs": ["evidence/worker-check.txt"],
            "artifact_revision": worker_revision,
        },
    ]
    write_json(output / "finding-dispositions.json", dispositions)

    if repair_round_limit == 0:
        ledger.append(
            "budget_exhausted",
            actor="coordinator",
            reason="A confirmed blocker exists and no repair round is authorized.",
            artifact_revision=worker_revision,
        )
        receipt = final_receipt(
            status="budget_exhausted",
            contract_identity=contract_identity,
            result_revision=worker_revision,
            integration_revision=None,
            source_line_count=source_lines_changed(
                workspace, base_revision, worker_revision
            ),
            repair_rounds_used=0,
            elapsed_seconds=round(time.monotonic() - started_at, 3),
            ledger=ledger,
            unresolved_findings=["F1"],
            human_decisions_required=[
                "Increase the repair-round limit under a revised contract or close the task."
            ],
        )
        write_json(output / "final-receipt.json", receipt)
        return 3

    ledger.append(
        "needs_fixes",
        actor="coordinator",
        reason="Confirmed F1 blocks acceptance; F2 was refuted by direct evidence.",
        artifact_revision=worker_revision,
    )
    ledger.append(
        "building",
        actor="fixture-worker",
        reason="Started the single authorized repair round for F1.",
        artifact_revision=worker_revision,
    )
    (workspace / "score.py").write_text(
        "def clamp_score(value: int) -> int:\n"
        "    return max(0, min(value, 100))\n",
        encoding="utf-8",
    )
    repaired_revision = commit(workspace, "fixture: repair confirmed lower-bound defect")
    repair_evidence = output / "evidence" / "repair-check.txt"
    if not run_score_check(workspace, repair_evidence):
        raise FixtureError("the bounded repair did not pass the declared check")
    ledger.append(
        "mechanical_check",
        actor="verifier",
        reason="Declared unit tests passed after the bounded repair.",
        artifact_revision=repaired_revision,
    )
    ledger.append(
        "critic_review",
        actor="coordinator",
        reason="Sealed the repaired revision and passing evidence for review.",
        artifact_revision=repaired_revision,
    )

    round_two_packet = review_packet(
        contract_identity=contract_identity,
        base_revision=worker_revision,
        result_revision=repaired_revision,
        artifact_diff=git(workspace, "diff", worker_revision, repaired_revision),
        check_status="passed",
        evidence_id="E2",
        evidence_content=repair_evidence.read_text(encoding="utf-8"),
        unresolved_findings=[],
    )
    second_verdict = run_critic(
        output,
        round_number=2,
        packet=round_two_packet,
        verdict=provider_verdict(
            repaired_revision,
            verdict="PASS",
            summary="The repaired revision satisfies both frozen commitments.",
            findings=[],
        ),
    )
    if second_verdict.get("verdict") != "PASS":
        raise FixtureError("round-two critic did not pass the repaired revision")
    ledger.append(
        "accepted_unit",
        actor="coordinator",
        reason="Checks passed and no adjudicated blocking finding remains.",
        artifact_revision=repaired_revision,
    )
    ledger.append(
        "integrating",
        actor="integrator",
        reason="Integrated the accepted unit as a separately identified artifact.",
        artifact_revision=repaired_revision,
    )
    write_json(
        workspace / "integration-manifest.json",
        {
            "contract_hash": contract_identity["contract_hash"],
            "accepted_unit_revision": repaired_revision,
            "finding_dispositions": ["F1:confirmed", "F2:refuted"],
        },
    )
    integration_revision = commit(workspace, "fixture: integrate accepted unit")
    integration_evidence = output / "evidence" / "integration-check.txt"
    if not run_score_check(workspace, integration_evidence):
        raise FixtureError("the integrated artifact failed its declared check")
    ledger.append(
        "final_review",
        actor="verifier",
        reason="Re-ran the declared check on the integrated artifact.",
        artifact_revision=integration_revision,
    )
    ledger.append(
        "completed",
        actor="coordinator",
        reason="The offline fixture completed with no consequential action pending.",
        artifact_revision=integration_revision,
    )

    receipt = final_receipt(
        status="completed",
        contract_identity=contract_identity,
        result_revision=repaired_revision,
        integration_revision=integration_revision,
        source_line_count=source_lines_changed(
            workspace, base_revision, repaired_revision
        ),
        repair_rounds_used=1,
        elapsed_seconds=round(time.monotonic() - started_at, 3),
        ledger=ledger,
        unresolved_findings=[],
        human_decisions_required=[],
    )
    receipt["evidence_refs"].extend(
        [
            "evidence/repair-check.txt",
            "critic-round-2/verdict.json",
            "evidence/integration-check.txt",
        ]
    )
    write_json(output / "final-receipt.json", receipt)
    print(output / "final-receipt.json")
    return 0


def main() -> int:
    args = parse_args()
    try:
        return execute(args.out_dir, args.repair_round_limit)
    except (FixtureError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"fixture error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
