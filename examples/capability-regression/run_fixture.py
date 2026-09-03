#!/usr/bin/env python3
"""Run one offline KLP v0.3 capability-preservation lifecycle."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from example_records import build_example_records
from klp_v03 import (
    ContractError,
    digest,
    validate_mission_snapshot,
    validate_task_binding,
)


ROOT = Path(__file__).resolve().parents[2]
CRITIC_SCRIPT = ROOT / "examples" / "openai-compatible-critic" / "critic.py"
VERDICT_SCHEMA = ROOT / "examples" / "openai-compatible-critic" / "verdict.schema.json"
CRITIC_FAMILY = "fixture-critic"
CRITIC_MODEL = "fixture-critic-v1"
WORKER_FAMILY = "fixture-worker"


class FixtureError(Exception):
    """Raised when the bounded fixture cannot establish its evidence."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--repair-round-limit", type=int, default=1)
    parser.add_argument(
        "--probe-mode", choices=("normal", "inconclusive"), default="normal"
    )
    parser.add_argument("--omit-capability-declaration", action="store_true")
    return parser.parse_args()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def write_terminal_receipt(
    output: Path,
    *,
    status: str,
    mission_identity: dict[str, object],
    contract_identity: dict[str, object],
    capability_report: dict[str, object],
    ledger: StateLedger,
    human_decisions_required: list[str],
) -> None:
    evidence_refs = sorted(
        {
            reference
            for value in capability_report.values()
            if isinstance(value, dict)
            for reference in value.get("evidence_refs", [])
            if isinstance(reference, str)
        }
    )
    write_json(
        output / "final-receipt.json",
        {
            "protocol": "klp-core/v0.3",
            "status": status,
            "mission_identity": mission_identity,
            "contract_identity": contract_identity,
            "capability_report": capability_report,
            "claims": [
                "The run stopped without claiming mission-preserving completion."
            ],
            "evidence_refs": evidence_refs,
            "limitations": [
                "This is an offline synthetic protocol fixture."
            ],
            "unresolved_findings": [],
            "human_decisions_required": human_decisions_required,
            "state_ledger_tail_hash": ledger.tail_hash,
        },
    )


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
    completed = subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
    )
    if check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise FixtureError(f"command failed ({' '.join(command)}): {detail}")
    return completed


def git(workspace: Path, *arguments: str) -> str:
    return run_command(["git", *arguments], cwd=workspace).stdout.strip()


def commit(workspace: Path, message: str) -> str:
    git(workspace, "add", "--all")
    git(workspace, "commit", "-q", "-m", message)
    return git(workspace, "rev-parse", "HEAD")


def integration_commit(workspace: Path, message: str) -> str:
    git(workspace, "commit", "--allow-empty", "-q", "-m", message)
    return git(workspace, "rev-parse", "HEAD")


class StateLedger:
    def __init__(
        self,
        path: Path,
        *,
        mission_revision: int,
        mission_hash: str,
        contract_revision: int,
    ) -> None:
        self.path = path
        self.mission_revision = mission_revision
        self.mission_hash = mission_hash
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
            "actor": actor,
            "reason": reason,
            "mission_revision": self.mission_revision,
            "mission_hash": self.mission_hash,
            "contract_revision": self.contract_revision,
            "artifact_revision": artifact_revision,
            "previous_event_hash": self.tail_hash,
        }
        self.tail_hash = digest(event)
        event["event_hash"] = self.tail_hash
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True) + "\n")
        self.state = new_state


class FakeCriticProvider:
    def __init__(self, verdict: dict[str, object]) -> None:
        self.verdict = verdict
        self.request_count = 0
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> "FakeCriticProvider":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
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


def provider_verdict(revision: str) -> dict[str, object]:
    return {
        "reviewed_revision": revision,
        "critic_provider_family": CRITIC_FAMILY,
        "critic_model": CRITIC_MODEL,
        "verdict": "PASS",
        "summary": "The narrow task commitments have passing declared checks.",
        "findings": [],
        "limitations": ["Synthetic critic response; no model-quality claim."],
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
    try:
        with FakeCriticProvider(verdict) as provider:
            completed = subprocess.run(
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
                env={
                    "PATH": os.environ.get("PATH", ""),
                    "LANG": "C.UTF-8",
                    "CRITIC_BASE_URL": provider.base_url,
                    "CRITIC_API_KEY": "fixture-only-key",
                    "CRITIC_MODEL": CRITIC_MODEL,
                    "CRITIC_PROVIDER_FAMILY": CRITIC_FAMILY,
                },
            )
            if completed.returncode != 0:
                raise FixtureError(
                    f"critic round {round_number} failed: {completed.stderr.strip()}"
                )
            if provider.request_count != 1:
                raise FixtureError("critic fixture expected exactly one loopback request")
    except OSError as exc:
        write_json(
            output / "evidence" / "critic-loopback-limitation.json",
            {"limitation": "127.0.0.1 loopback binding unavailable", "error": str(exc)},
        )
        raise FixtureError(f"127.0.0.1 loopback binding unavailable: {exc}") from exc
    value = json.loads((critic_output / "verdict.json").read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FixtureError("critic verdict artifact must be an object")
    return value


def adaptive_chooser() -> str:
    return (
        "def choose_action(signal: str) -> dict[str, str]:\n"
        "    actions = {\"fire\": \"evacuate\", \"medical\": \"assist\"}\n"
        "    return {\n"
        "        \"action\": actions.get(signal, \"observe\"),\n"
        "        \"decision_source\": \"input-dependent\",\n"
        "    }\n"
    )


def fixed_chooser() -> str:
    return (
        "def choose_action(signal: str) -> dict[str, str]:\n"
        "    return {\"action\": \"observe\", \"decision_source\": \"fixed-policy\"}\n"
    )


def setup_workspace(workspace: Path) -> str:
    workspace.mkdir()
    git(workspace, "init", "-q", "--initial-branch=main")
    git(workspace, "config", "user.name", "KLP Fixture")
    git(workspace, "config", "user.email", "fixture@example.invalid")
    (workspace / "tests").mkdir()
    (workspace / "chooser.py").write_text(adaptive_chooser(), encoding="utf-8")
    (workspace / "tests" / "test_chooser.py").write_text(
        "import unittest\n\n"
        "from chooser import choose_action\n\n\n"
        "class ChooserTaskTests(unittest.TestCase):\n"
        "    def test_response_shape_and_allowed_vocabulary(self) -> None:\n"
        "        for signal in (\"fire\", \"medical\", \"unknown\"):\n"
        "            response = choose_action(signal)\n"
        "            self.assertEqual({\"action\", \"decision_source\"}, set(response))\n"
        "            self.assertIn(response[\"action\"], {\"evacuate\", \"assist\", \"observe\"})\n\n\n"
        "if __name__ == \"__main__\":\n"
        "    unittest.main()\n",
        encoding="utf-8",
    )
    (workspace / "capability_probe.py").write_text(
        "import json\n\n"
        "from chooser import choose_action\n\n\n"
        "responses = {signal: choose_action(signal) for signal in (\"fire\", \"medical\", \"unknown\")}\n"
        "actions = {signal: response[\"action\"] for signal, response in responses.items()}\n"
        "decision_sources = sorted({response[\"decision_source\"] for response in responses.values()})\n"
        "observations = {\n"
        "    \"actions\": actions,\n"
        "    \"decision_sources\": decision_sources,\n"
        "    \"outputs_are_not_constant\": len(set(actions.values())) > 1,\n"
        "}\n"
        "passed = (\n"
        "    actions == {\"fire\": \"evacuate\", \"medical\": \"assist\", \"unknown\": \"observe\"}\n"
        "    and observations[\"outputs_are_not_constant\"]\n"
        "    and decision_sources == [\"input-dependent\"]\n"
        ")\n"
        "print(json.dumps(observations, sort_keys=True))\n"
        "raise SystemExit(0 if passed else 1)\n",
        encoding="utf-8",
    )
    return commit(workspace, "fixture: establish accepted adaptive baseline")


def run_task_check(workspace: Path, evidence_path: Path) -> bool:
    completed = run_command(
        [
            sys.executable,
            "-B",
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-v",
        ],
        cwd=workspace,
        check=False,
    )
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        completed.stdout + completed.stderr, encoding="utf-8"
    )
    return completed.returncode == 0


def require_clean_workspace(workspace: Path, *, boundary: str) -> None:
    status = git(workspace, "status", "--short", "--untracked-files=all")
    if status:
        raise FixtureError(
            f"capability probe requires a clean workspace {boundary}: {status}"
        )


def run_capability_probe(
    workspace: Path,
    evidence_path: Path,
    *,
    mission_hash: str,
    artifact_revision: str,
    baseline_revision: str,
    force_inconclusive: bool = False,
) -> dict[str, object]:
    require_clean_workspace(workspace, boundary="before execution")
    if force_inconclusive:
        result = "inconclusive"
        observations: dict[str, object] = {"reason": "fixture-forced-inconclusive"}
    else:
        completed = run_command(
            [sys.executable, "-B", "capability_probe.py"],
            cwd=workspace,
            check=False,
        )
        try:
            observations = json.loads(completed.stdout)
        except json.JSONDecodeError:
            observations = {"stdout": completed.stdout, "stderr": completed.stderr}
            result = "inconclusive"
        else:
            result = "passed" if completed.returncode == 0 else "failed"
    require_clean_workspace(workspace, boundary="after execution")

    record = {
        "capability_id": "adaptive-choice",
        "mission_hash": mission_hash,
        "artifact_revision": artifact_revision,
        "baseline_revision": baseline_revision,
        "positive_control": ["fire -> evacuate", "medical -> assist"],
        "negative_control": ["unknown -> observe", "outputs are not constant"],
        "expected_observations": {"decision_source": "input-dependent"},
        "actual_observations": observations,
        "decision_provenance": observations.get("decision_sources", []),
        "auditor_identity": "capability-auditor",
        "limits": {"external_cost_usd": 0, "attempts": 1},
        "result": result,
        "evidence_refs": [str(evidence_path.relative_to(evidence_path.parents[1]))],
    }
    write_json(evidence_path, record)
    return record


def capability_commitments(mission: dict[str, object]) -> list[dict[str, object]]:
    body = mission["mission"]
    assert isinstance(body, dict)
    return [
        {
            "capability_id": capability["capability_id"],
            "required_behavior": capability["required_behavior"],
            "forbidden_regressions": body["forbidden_regressions"],
            "decision_provenance_requirement": capability[
                "decision_provenance_requirement"
            ],
        }
        for capability in body["critical_capabilities"]
    ]


def review_packet(
    *,
    mission_snapshot: dict[str, object],
    task_snapshot: dict[str, object],
    base_revision: str,
    result_revision: str,
    artifact_diff: str,
    evidence_content: str,
) -> dict[str, object]:
    mission_identity = mission_snapshot["identity"]
    task_identity = task_snapshot["identity"]
    task = task_snapshot["task"]
    assert isinstance(task_identity, dict)
    assert isinstance(task, dict)
    return {
        "protocol": "klp-core/v0.3",
        "task_id": task_identity["task_id"],
        "contract_id": task_identity["task_id"],
        "contract_revision": task_identity["task_revision"],
        "contract_hash": task_identity["contract_hash"],
        "objective": task["objective"],
        "commitments": [
            {
                "id": "task-shape",
                "text": "Return the declared response shape and allowed action vocabulary.",
            }
        ],
        "worker_provider_family": WORKER_FAMILY,
        "base_revision": base_revision,
        "result_revision": result_revision,
        "changed_files": ["chooser.py"],
        "artifact_diff": artifact_diff,
        "checks": [
            {
                "name": "declared-task-unit-test",
                "command": "python3 -B -m unittest discover -s tests -v",
                "status": "passed",
                "evidence_ref": "task-check",
            }
        ],
        "evidence": [
            {"id": "task-check", "kind": "test-output", "content": evidence_content}
        ],
        "known_limitations": ["The fixture worker and critic are scripted."],
        "unresolved_findings": [],
        "mission_identity": mission_identity,
        "affected_capabilities": task["affected_capabilities"],
        "capability_commitments": capability_commitments(mission_snapshot),
        "expected_capability_delta": task["expected_capability_delta"],
        "required_capability_probes": task["required_capability_probes"],
        "baseline_evidence_refs": task["baseline_evidence_refs"],
    }


def mission_check(
    output: Path,
    name: str,
    *,
    mission_hash: str,
    artifact_revision: str,
) -> None:
    write_json(
        output / "evidence" / name,
        {
            "mission_hash": mission_hash,
            "artifact_revision": artifact_revision,
            "result": "passed",
            "mission_amendment_required": False,
            "reason": "The bounded repair preserves the frozen adaptive-choice mission.",
        },
    )


def execute(
    output: Path,
    repair_round_limit: int,
    *,
    probe_mode: str,
    omit_capability_declaration: bool,
) -> int:
    if repair_round_limit not in (0, 1):
        raise FixtureError("repair round limit must be zero or one")
    prepare_output(output)
    records = build_example_records()
    mission_snapshot = records["mission-contract.example.json"]
    task_snapshot = records["task-contract.example.json"]
    if omit_capability_declaration:
        task_snapshot = json.loads(json.dumps(task_snapshot))
        task = task_snapshot["task"]
        assert isinstance(task, dict)
        task["affected_capabilities"] = []
    validate_mission_snapshot(mission_snapshot)
    changed_surfaces = ["path:chooser.py", "interface:choose_action"]

    mission_identity = mission_snapshot["identity"]
    task_identity = task_snapshot["identity"]
    assert isinstance(mission_identity, dict)
    assert isinstance(task_identity, dict)
    mission_hash = str(mission_identity["mission_hash"])
    ledger = StateLedger(
        output / "state-events.jsonl",
        mission_revision=int(mission_identity["mission_revision"]),
        mission_hash=mission_hash,
        contract_revision=int(task_identity["task_revision"]),
    )
    ledger.append(
        "draft",
        actor="fixture-author",
        reason="Created the offline capability-preservation fixture.",
        artifact_revision=None,
    )
    write_json(output / "mission.snapshot.json", mission_snapshot)
    write_json(output / "task.snapshot.json", task_snapshot)
    try:
        triggered = validate_task_binding(
            mission_snapshot, task_snapshot, changed_surfaces
        )
    except ContractError as exc:
        ledger.append(
            "mission_mismatch",
            actor="mission-custodian",
            reason=f"Task Contract validation stopped the fixture: {exc}",
            artifact_revision=None,
        )
        write_terminal_receipt(
            output,
            status="mission_mismatch",
            mission_identity=mission_identity,
            contract_identity=task_identity,
            capability_report={
                "adaptive-choice": {
                    "before": "not_run",
                    "after": "not_run",
                    "disposition": "unproven",
                    "reason": str(exc),
                    "evidence_refs": [],
                }
            },
            ledger=ledger,
            human_decisions_required=[
                "Submit a Task Contract that declares every triggered critical capability."
            ],
        )
        return 5

    task = task_snapshot["task"]
    assert isinstance(task, dict)
    workspace = output / "workspace"
    baseline_revision = setup_workspace(workspace)
    ledger.append(
        "mission_binding_check",
        actor="mission-custodian",
        reason="Validated the frozen Mission Contract against changed surfaces.",
        artifact_revision=baseline_revision,
    )
    write_json(
        output / "mission-binding-report.json",
        {
            "mission_identity": mission_identity,
            "contract_identity": task_identity,
            "changed_surfaces": changed_surfaces,
            "triggered_capabilities": sorted(triggered),
            "declared_capabilities": task["affected_capabilities"],
            "actor": "mission-custodian",
            "execution_coordinator": "execution-coordinator",
            "result": "passed",
        },
    )
    ledger.append(
        "approved",
        actor="mission-custodian",
        reason="The task preserves the declared adaptive-choice capability.",
        artifact_revision=baseline_revision,
    )
    ledger.append(
        "capability_baseline",
        actor="capability-auditor",
        reason="Captured the accepted product-truth baseline.",
        artifact_revision=baseline_revision,
    )
    baseline = run_capability_probe(
        workspace,
        output / "evidence" / "capability-baseline.json",
        mission_hash=mission_hash,
        artifact_revision=baseline_revision,
        baseline_revision=baseline_revision,
    )
    if baseline["result"] != "passed":
        raise FixtureError("accepted baseline did not pass the capability probe")

    ledger.append(
        "assigned",
        actor="execution-coordinator",
        reason="Assigned the bounded worker unit.",
        artifact_revision=baseline_revision,
    )
    ledger.append(
        "building",
        actor="fixture-worker",
        reason="Produced the scripted fixed-policy worker revision.",
        artifact_revision=baseline_revision,
    )
    (workspace / "chooser.py").write_text(fixed_chooser(), encoding="utf-8")
    worker_revision = commit(workspace, "fixture: replace adaptive choice with fixed policy")
    worker_check = output / "evidence" / "worker-check.txt"
    if not run_task_check(workspace, worker_check):
        raise FixtureError("fixed-policy worker revision did not pass the declared task check")
    ledger.append(
        "mechanical_check",
        actor="verifier",
        reason="The declared task-level test passed on the fixed-policy revision.",
        artifact_revision=worker_revision,
    )
    write_json(
        output / "evidence" / "restriction-candidate.json",
        {
            "status": "requires-preservation-proof",
            "change_kind": "replace-adaptive-with-fixed-sequence",
            "affected_capabilities": ["adaptive-choice"],
            "worker_revision": worker_revision,
            "direct_diff_evidence": git(
                workspace, "diff", baseline_revision, worker_revision, "--", "chooser.py"
            ),
        },
    )
    ledger.append(
        "critic_review",
        actor="execution-coordinator",
        reason="Sealed the passing task evidence and exact worker revision for review.",
        artifact_revision=worker_revision,
    )
    first_verdict = run_critic(
        output,
        round_number=1,
        packet=review_packet(
            mission_snapshot=mission_snapshot,
            task_snapshot=task_snapshot,
            base_revision=baseline_revision,
            result_revision=worker_revision,
            artifact_diff=git(workspace, "diff", baseline_revision, worker_revision),
            evidence_content=worker_check.read_text(encoding="utf-8"),
        ),
        verdict=provider_verdict(worker_revision),
    )
    if first_verdict.get("verdict") != "PASS":
        raise FixtureError("first scripted critic did not return PASS")
    ledger.append(
        "accepted_unit",
        actor="execution-coordinator",
        reason="The task-level critic accepted the narrow worker commitments.",
        artifact_revision=worker_revision,
    )
    ledger.append(
        "integrating",
        actor="execution-coordinator",
        reason="Created the first integrated artifact for product-truth probing.",
        artifact_revision=worker_revision,
    )
    integration_one = integration_commit(workspace, "fixture: integrate fixed-policy candidate")
    ledger.append(
        "capability_check",
        actor="capability-auditor",
        reason="Ran the product-truth probe against the first integrated artifact.",
        artifact_revision=integration_one,
    )
    first_capability = run_capability_probe(
        workspace,
        output / "evidence" / "capability-after-integration-1.json",
        mission_hash=mission_hash,
        artifact_revision=integration_one,
        baseline_revision=baseline_revision,
        force_inconclusive=probe_mode == "inconclusive",
    )
    if first_capability["result"] == "inconclusive":
        ledger.append(
            "capability_unproven",
            actor="capability-auditor",
            reason="The first post-integration capability probe was inconclusive.",
            artifact_revision=integration_one,
        )
        write_terminal_receipt(
            output,
            status="capability_unproven",
            mission_identity=mission_identity,
            contract_identity=task_identity,
            capability_report={
                "adaptive-choice": {
                    "before": "passed",
                    "after": "inconclusive",
                    "disposition": "unproven",
                    "evidence_refs": [
                        "evidence/capability-baseline.json",
                        "evidence/capability-after-integration-1.json",
                    ],
                }
            },
            ledger=ledger,
            human_decisions_required=[
                "Resolve the capability probe before authorizing repair or completion."
            ],
        )
        return 4
    if first_capability["result"] != "failed":
        raise FixtureError("fixed-policy integration did not trigger capability regression")
    ledger.append(
        "capability_regression",
        actor="capability-auditor",
        reason="The integrated artifact failed the adaptive-choice product-truth probe.",
        artifact_revision=integration_one,
    )
    write_json(
        output / "evidence" / "restriction-disposition-1.json",
        {
            "status": "blocking",
            "candidate_ref": "evidence/restriction-candidate.json",
            "artifact_revision": integration_one,
            "evidence_refs": ["evidence/capability-after-integration-1.json"],
        },
    )
    if repair_round_limit == 0:
        ledger.append(
            "budget_exhausted",
            actor="execution-coordinator",
            reason="The authorized repair-round budget was exhausted after regression.",
            artifact_revision=integration_one,
        )
        write_terminal_receipt(
            output,
            status="budget_exhausted",
            mission_identity=mission_identity,
            contract_identity=task_identity,
            capability_report={
                "adaptive-choice": {
                    "before": "passed",
                    "after": "failed",
                    "disposition": "degraded",
                    "evidence_refs": [
                        "evidence/capability-baseline.json",
                        "evidence/capability-after-integration-1.json",
                    ],
                }
            },
            ledger=ledger,
            human_decisions_required=[
                "Authorize another repair round or amend the frozen mission."
            ],
        )
        return 3
    mission_check(
        output,
        "repair-mission-check.json",
        mission_hash=mission_hash,
        artifact_revision=integration_one,
    )
    ledger.append(
        "building",
        actor="fixture-worker",
        reason="Started the one authorized repair round after capability regression.",
        artifact_revision=integration_one,
    )
    (workspace / "chooser.py").write_text(adaptive_chooser(), encoding="utf-8")
    repaired_revision = commit(workspace, "fixture: restore input-dependent choice")
    repair_check = output / "evidence" / "repair-check.txt"
    if not run_task_check(workspace, repair_check):
        raise FixtureError("repair revision did not pass the declared task check")
    ledger.append(
        "mechanical_check",
        actor="verifier",
        reason="The declared task-level test passed after the bounded repair.",
        artifact_revision=repaired_revision,
    )
    ledger.append(
        "critic_review",
        actor="execution-coordinator",
        reason="Sealed the repaired revision for a fresh critic review.",
        artifact_revision=repaired_revision,
    )
    second_verdict = run_critic(
        output,
        round_number=2,
        packet=review_packet(
            mission_snapshot=mission_snapshot,
            task_snapshot=task_snapshot,
            base_revision=integration_one,
            result_revision=repaired_revision,
            artifact_diff=git(workspace, "diff", integration_one, repaired_revision),
            evidence_content=repair_check.read_text(encoding="utf-8"),
        ),
        verdict=provider_verdict(repaired_revision),
    )
    if second_verdict.get("verdict") != "PASS":
        raise FixtureError("second scripted critic did not return PASS")
    ledger.append(
        "accepted_unit",
        actor="execution-coordinator",
        reason="The repaired task-level unit received a fresh PASS verdict.",
        artifact_revision=repaired_revision,
    )
    ledger.append(
        "integrating",
        actor="execution-coordinator",
        reason="Created the repaired integrated artifact for product-truth probing.",
        artifact_revision=repaired_revision,
    )
    integration_two = integration_commit(workspace, "fixture: integrate repaired candidate")
    ledger.append(
        "capability_check",
        actor="capability-auditor",
        reason="Ran the product-truth probe against the repaired integration.",
        artifact_revision=integration_two,
    )
    second_capability = run_capability_probe(
        workspace,
        output / "evidence" / "capability-after-integration-2.json",
        mission_hash=mission_hash,
        artifact_revision=integration_two,
        baseline_revision=baseline_revision,
    )
    if second_capability["result"] != "passed":
        raise FixtureError("repaired integration did not preserve adaptive choice")
    write_json(
        output / "evidence" / "restriction-disposition-2.json",
        {
            "status": "cleared",
            "candidate_ref": "evidence/restriction-candidate.json",
            "artifact_revision": integration_two,
            "evidence_refs": ["evidence/capability-after-integration-2.json"],
        },
    )
    mission_check(
        output,
        "final-mission-check.json",
        mission_hash=mission_hash,
        artifact_revision=integration_two,
    )
    ledger.append(
        "final_review",
        actor="mission-custodian",
        reason="Confirmed the repaired integration preserves the frozen mission.",
        artifact_revision=integration_two,
    )
    ledger.append(
        "completed",
        actor="execution-coordinator",
        reason="Task evidence, fresh criticism, and capability proof all passed.",
        artifact_revision=integration_two,
    )
    write_json(
        output / "final-receipt.json",
        {
            "protocol": "klp-core/v0.3",
            "mission_identity": mission_identity,
            "contract_identity": task_identity,
            "status": "completed",
            "capability_report": {
                "adaptive-choice": {
                    "before": "passed",
                    "after": "passed",
                    "intermediate": "failed",
                    "disposition": "preserved",
                    "evidence_refs": [
                        "evidence/capability-baseline.json",
                        "evidence/capability-after-integration-1.json",
                        "evidence/capability-after-integration-2.json",
                    ],
                }
            },
            "measured_budget": {"repair_rounds_used": 1, "external_cost_usd": 0},
            "limitations": [
                "The worker and critic are scripted.",
                "The fixture proves protocol gating, not model quality or production safety.",
            ],
            "state_ledger_tail_hash": ledger.tail_hash,
        },
    )
    return 0


def main() -> int:
    args = parse_args()
    try:
        return execute(
            args.out_dir,
            args.repair_round_limit,
            probe_mode=args.probe_mode,
            omit_capability_declaration=args.omit_capability_declaration,
        )
    except FixtureError as exc:
        print(f"fixture error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
