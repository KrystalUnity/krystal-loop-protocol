"""Build and write deterministic KLP Core v0.3 example records."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from klp_v03 import PROTOCOL_VERSION, digest


CREATED_AT = "2026-09-03T00:00:00Z"
RECORDS_DIR = Path(__file__).resolve().parent / "records"


def _mission_body() -> dict[str, Any]:
    return {
        "product_outcome": "Select the appropriate safe action from each supplied signal.",
        "critical_capabilities": [
            {
                "capability_id": "adaptive-choice",
                "required_behavior": "Select different actions for different supported signals.",
                "severity": "critical",
                "trigger_rules": [
                    "path:chooser.py",
                    "interface:choose_action",
                    "config:decision-policy",
                ],
                "positive_control": ["fire -> evacuate", "medical -> assist"],
                "negative_control": [
                    "unknown -> observe",
                    "outputs are not constant",
                    "decision_source == input-dependent",
                ],
                "proof_method": "Run the bounded adaptive-choice product-truth probe.",
                "accepted_baseline_ref": "evidence:adaptive-choice-baseline-001",
                "decision_provenance_requirement": "decision_source must be input-dependent.",
            }
        ],
        "forbidden_regressions": [
            "Replace input-dependent choice with a fixed output.",
            "Move product judgment into a pre-authored answer.",
        ],
        "operator_revision_authority": "Only the human operator may amend this mission.",
        "revision_reason": "Initial capability-preservation mission for the offline fixture.",
    }


def build_example_records() -> dict[str, dict[str, Any]]:
    mission_body = _mission_body()
    mission_hash = digest(mission_body)
    mission = {
        "identity": {
            "protocol_version": PROTOCOL_VERSION,
            "mission_id": "klp-capability-regression",
            "mission_revision": 1,
            "mission_hash": mission_hash,
            "parent_mission_hash": None,
            "authority_ref": "operator-decision:fixture-000",
            "created_at": CREATED_AT,
        },
        "mission": mission_body,
    }
    task_body = {
        "task_id": "build-adaptive-choice-fixture",
        "objective": "Preserve adaptive choices while making the fixture implementation explicit.",
        "mission_id": mission["identity"]["mission_id"],
        "mission_revision": mission["identity"]["mission_revision"],
        "mission_hash": mission_hash,
        "affected_capabilities": ["adaptive-choice"],
        "expected_capability_delta": "preserve",
        "required_capability_probes": ["adaptive-choice-product-truth"],
        "baseline_evidence_refs": ["evidence:adaptive-choice-baseline-001"],
        "allowed_paths": ["chooser.py"],
    }
    task = {
        "identity": {
            "protocol_version": PROTOCOL_VERSION,
            "task_id": task_body["task_id"],
            "task_revision": 1,
            "contract_hash": digest(task_body),
            "created_at": CREATED_AT,
        },
        "task": task_body,
    }
    amendment = {
        "protocol_version": PROTOCOL_VERSION,
        "request_id": "mission-amendment-fixed-choice",
        "mission_id": mission["identity"]["mission_id"],
        "current_mission_hash": mission_hash,
        "requested_change": "Permit a fixed safe action for every signal.",
        "technical_explanation": {
            "fields_changed": [
                "mission.critical_capabilities[0].required_behavior",
                "mission.critical_capabilities[0].negative_control",
            ],
            "evidence_refs": ["evidence:adaptive-choice-regression-001"],
            "behavioral_impact": "The chooser could return one safe action for every signal.",
            "architectural_impact": "Input-dependent decision logic could be replaced by a fixed policy.",
            "testing_impact": "The positive and negative controls would need new acceptance criteria.",
            "safety_impact": "A fixed action may be safer for some signals but less appropriate for others.",
            "compatibility_impact": "Clients expecting distinct supported actions may observe the same action.",
            "alternatives_considered": [
                "Keep adaptive selection and narrow only the unsafe input handling.",
                "Add bounded fallback behavior without changing supported choices.",
            ],
            "rollback_implications": "Restore the prior mission revision and adaptive implementation.",
            "duration": "Permanent unless a later operator-authorized amendment supersedes it.",
        },
        "operator_impact_statement": {
            "today": "Today the product selects different actions from the supplied signal.",
            "after": "After this amendment, it may return one fixed safe action.",
            "user_may_lose": "Users may lose adaptive decisions for supported signals.",
            "expected_benefit": "The fixed action would reduce decision variability.",
            "if_declined": "The current adaptive capability and its existing limits remain.",
        },
    }
    return {
        "mission-contract.example.json": mission,
        "task-contract.example.json": task,
        "mission-amendment.example.json": amendment,
    }


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main() -> int:
    for name, record in build_example_records().items():
        _write_json(RECORDS_DIR / name, record)
    return 0


if __name__ == "__main__":
    sys.exit(main())
