from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


FIXTURE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIXTURE_DIR))

from example_records import build_example_records  # noqa: E402
from klp_v03 import (  # noqa: E402
    ContractError,
    build_authorized_mission_revision,
    digest,
    validate_amendment_request,
    validate_mission_snapshot,
    validate_task_binding,
)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = build_example_records()
        self.mission = self.records["mission-contract.example.json"]
        self.task = self.records["task-contract.example.json"]

    def resign_task(self, task: dict[str, object]) -> None:
        task["identity"]["contract_hash"] = digest(task["task"])

    def proposed_mission_body(self) -> dict[str, object]:
        body = copy.deepcopy(self.mission["mission"])
        body["critical_capabilities"][0]["required_behavior"] = (
            "Return one fixed safe action for every signal."
        )
        body["critical_capabilities"][0]["negative_control"] = [
            "unknown -> observe",
            "outputs may be constant",
            "decision_source == fixed-policy",
        ]
        body["revision_reason"] = (
            "Operator approved the fixed-choice mission amendment."
        )
        return body

    def test_example_records_are_valid_and_digest_bound(self) -> None:
        body = validate_mission_snapshot(self.mission)
        self.assertEqual(digest(body), self.mission["identity"]["mission_hash"])
        triggered = validate_task_binding(
            self.mission, self.task, ["path:chooser.py"]
        )
        self.assertEqual({"adaptive-choice"}, triggered)
        self.assertEqual(1, self.task["task"]["limits"]["repair_rounds"])
        self.assertIn("coordinator_may", self.task["task"]["delegation"])
        self.assertIn("must_escalate", self.task["task"]["delegation"])
        validate_amendment_request(
            self.records["mission-amendment.example.json"]
        )

    def test_stale_mission_hash_is_rejected(self) -> None:
        task = copy.deepcopy(self.task)
        task["task"]["mission_hash"] = "sha256:stale"
        with self.assertRaisesRegex(ContractError, "mission hash"):
            validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_triggered_but_undeclared_capability_is_rejected(self) -> None:
        task = copy.deepcopy(self.task)
        task["task"]["affected_capabilities"] = []
        with self.assertRaisesRegex(ContractError, "adaptive-choice"):
            validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_affected_capability_requires_exact_accepted_baseline_ref(self) -> None:
        cases = (
            ("missing", None),
            ("empty", []),
            ("unrelated", ["evidence:unrelated-baseline"]),
        )
        for name, baseline_refs in cases:
            with self.subTest(name=name):
                task = copy.deepcopy(self.task)
                if baseline_refs is None:
                    task["task"].pop("baseline_evidence_refs")
                else:
                    task["task"]["baseline_evidence_refs"] = baseline_refs
                self.resign_task(task)
                with self.assertRaisesRegex(ContractError, "baseline_evidence_refs"):
                    validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_task_authority_and_limits_are_validated_inside_digest(self) -> None:
        malformed = (
            ("limits", {"repair_rounds": -1, "elapsed_seconds": 60, "external_cost_usd": 0}),
            ("limits", {"repair_rounds": 1, "elapsed_seconds": 0, "external_cost_usd": 0}),
            ("limits", {"repair_rounds": 1, "elapsed_seconds": 60, "external_cost_usd": float("nan")}),
            ("delegation", {"coordinator_may": [], "must_escalate": ["increase a declared limit"]}),
        )
        for field, value in malformed:
            with self.subTest(field=field, value=value):
                task = copy.deepcopy(self.task)
                task["task"][field] = value
                self.resign_task(task)
                with self.assertRaisesRegex(ContractError, field):
                    validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_malformed_capability_delta_types_raise_contract_error(self) -> None:
        for malformed in (["preserve"], {"value": "preserve"}):
            with self.subTest(malformed=malformed):
                task = copy.deepcopy(self.task)
                task["task"]["expected_capability_delta"] = malformed
                self.resign_task(task)
                with self.assertRaisesRegex(
                    ContractError,
                    "task.expected_capability_delta must be preserve or improve",
                ):
                    validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_amendment_requires_both_explanations(self) -> None:
        request = copy.deepcopy(
            self.records["mission-amendment.example.json"]
        )
        request.pop("operator_impact_statement")
        with self.assertRaisesRegex(ContractError, "plain-English"):
            validate_amendment_request(request)

        request = copy.deepcopy(
            self.records["mission-amendment.example.json"]
        )
        request.pop("technical_explanation")
        with self.assertRaisesRegex(ContractError, "technical_explanation"):
            validate_amendment_request(request)

        request = copy.deepcopy(
            self.records["mission-amendment.example.json"]
        )
        request["operator_impact_statement"]["after"] = ""
        with self.assertRaisesRegex(
            ContractError, "operator_impact_statement.after"
        ):
            validate_amendment_request(request)

        validate_amendment_request(
            self.records["mission-amendment.example.json"]
        )

    def test_amendment_requires_v03_protocol_version(self) -> None:
        for protocol_version in (None, "klp-core/v0.2"):
            with self.subTest(protocol_version=protocol_version):
                request = copy.deepcopy(
                    self.records["mission-amendment.example.json"]
                )
                if protocol_version is None:
                    request.pop("protocol_version", None)
                else:
                    request["protocol_version"] = protocol_version
                with self.assertRaisesRegex(ContractError, "protocol_version"):
                    validate_amendment_request(request)

    def test_malformed_digest_syntax_is_rejected(self) -> None:
        malformed_digests = (
            "sha256:" + "a" * 63,
            "sha256:" + "a" * 65,
            "sha256:" + "g" * 64,
        )
        for malformed_digest in malformed_digests:
            with self.subTest(malformed_digest=malformed_digest):
                mission = copy.deepcopy(self.mission)
                mission["identity"]["mission_hash"] = malformed_digest
                with self.assertRaisesRegex(ContractError, "sha256 digest"):
                    validate_mission_snapshot(mission)

    def test_committed_examples_match_the_generator(self) -> None:
        records_dir = FIXTURE_DIR / "records"
        for name, expected in self.records.items():
            actual = json.loads((records_dir / name).read_text(encoding="utf-8"))
            self.assertEqual(expected, actual)

    def test_authorized_revision_preserves_parent_and_authority(self) -> None:
        body = self.proposed_mission_body()
        revised = build_authorized_mission_revision(
            self.mission,
            self.records["mission-amendment.example.json"],
            body,
            "operator-decision:fixture-001",
        )
        self.assertEqual(2, revised["identity"]["mission_revision"])
        self.assertEqual(
            self.mission["identity"]["mission_hash"],
            revised["identity"]["parent_mission_hash"],
        )
        self.assertEqual(
            "operator-decision:fixture-001",
            revised["identity"]["authority_ref"],
        )
        self.assertEqual(
            "Operator approved the fixed-choice mission amendment.",
            revised["mission"]["revision_reason"],
        )

    def test_amendment_rejects_undeclared_authority_field_change(self) -> None:
        body = self.proposed_mission_body()
        body["operator_revision_authority"] = "The coordinator may amend the mission."
        request = copy.deepcopy(self.records["mission-amendment.example.json"])
        request["proposed_mission_hash"] = digest(body)
        with self.assertRaisesRegex(ContractError, "undeclared mission field change"):
            build_authorized_mission_revision(
                self.mission, request, body, "operator-decision:fixture-001"
            )

    def test_amendment_rejects_overbroad_field_declaration(self) -> None:
        body = self.proposed_mission_body()
        request = copy.deepcopy(self.records["mission-amendment.example.json"])
        request["technical_explanation"]["fields_changed"] = ["mission"]
        with self.assertRaisesRegex(ContractError, "exactly match"):
            build_authorized_mission_revision(
                self.mission, request, body, "operator-decision:fixture-001"
            )

    def test_amendment_rejects_stale_revision_reason(self) -> None:
        body = self.proposed_mission_body()
        stale_reason = self.mission["mission"]["revision_reason"]
        body["revision_reason"] = stale_reason
        request = copy.deepcopy(self.records["mission-amendment.example.json"])
        request["proposed_revision_reason"] = stale_reason
        request["proposed_mission_hash"] = digest(body)
        with self.assertRaisesRegex(ContractError, "fresh revision reason"):
            build_authorized_mission_revision(
                self.mission, request, body, "operator-decision:fixture-001"
            )

    def test_amendment_rejects_mismatched_proposed_body_digest(self) -> None:
        body = self.proposed_mission_body()
        body["product_outcome"] = "A body not sealed by the approved request."
        with self.assertRaisesRegex(ContractError, "proposed mission body"):
            build_authorized_mission_revision(
                self.mission,
                self.records["mission-amendment.example.json"],
                body,
                "operator-decision:fixture-001",
            )


if __name__ == "__main__":
    unittest.main()
