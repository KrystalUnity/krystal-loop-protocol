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
    digest,
    validate_amendment_request,
    build_authorized_mission_revision,
    validate_mission_snapshot,
    validate_task_binding,
)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = build_example_records()
        self.mission = self.records["mission-contract.example.json"]
        self.task = self.records["task-contract.example.json"]

    def test_example_records_are_valid_and_digest_bound(self) -> None:
        body = validate_mission_snapshot(self.mission)
        self.assertEqual(digest(body), self.mission["identity"]["mission_hash"])
        triggered = validate_task_binding(
            self.mission, self.task, ["path:chooser.py"]
        )
        self.assertEqual({"adaptive-choice"}, triggered)
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
        body = copy.deepcopy(self.mission["mission"])
        body["critical_capabilities"][0]["required_behavior"] = (
            "Return one fixed safe action for every signal."
        )
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


if __name__ == "__main__":
    unittest.main()
