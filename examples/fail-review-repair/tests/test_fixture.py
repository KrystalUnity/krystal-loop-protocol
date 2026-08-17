from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "examples" / "fail-review-repair" / "run_fixture.py"


def canonical_json(value: object) -> bytes:
    return json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")


class FailReviewRepairFixtureTests(unittest.TestCase):
    def run_fixture(
        self, output: Path, *, repair_round_limit: int = 1
    ) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "LANG": "C.UTF-8",
        }
        return subprocess.run(
            [
                sys.executable,
                str(FIXTURE),
                "--out-dir",
                str(output),
                "--repair-round-limit",
                str(repair_round_limit),
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )

    def read_json(self, path: Path) -> dict[str, object]:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def test_fixture_proves_one_bounded_fail_review_repair_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture-output"
            result = self.run_fixture(output)

            self.assertEqual(0, result.returncode, result.stderr)

            contract_record = self.read_json(output / "contract.snapshot.json")
            contract = contract_record["contract"]
            identity = contract_record["identity"]
            self.assertIsInstance(contract, dict)
            self.assertIsInstance(identity, dict)
            self.assertEqual("klp-fixture-clamp-score", identity["contract_id"])
            self.assertEqual(1, identity["revision"])
            self.assertIsNone(identity["parent_contract_hash"])
            self.assertEqual(
                "json-sorted-compact-utf8", identity.get("canonicalization")
            )
            self.assertEqual(
                hashlib.sha256(canonical_json(contract)).hexdigest(),
                identity["contract_hash"],
            )
            self.assertEqual(1, contract["limits"]["repair_rounds"])
            self.assertIn("coordinator_may", contract["delegation"])
            self.assertIn("must_escalate", contract["delegation"])

            events = [
                json.loads(line)
                for line in (output / "state-events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            states = [event["new_state"] for event in events]
            self.assertEqual(
                [
                    "draft",
                    "authorized",
                    "assigned",
                    "building",
                    "mechanical_check",
                    "critic_review",
                    "needs_fixes",
                    "building",
                    "mechanical_check",
                    "critic_review",
                    "accepted_unit",
                    "integrating",
                    "final_review",
                    "completed",
                ],
                states,
            )
            previous_hash = None
            for sequence, event in enumerate(events, start=1):
                self.assertEqual(sequence, event["sequence"])
                self.assertEqual(previous_hash, event["previous_event_hash"])
                event_hash = event.pop("event_hash")
                self.assertEqual(
                    hashlib.sha256(canonical_json(event)).hexdigest(), event_hash
                )
                previous_hash = event_hash

            bad_check = (output / "evidence" / "worker-check.txt").read_text(
                encoding="utf-8"
            )
            repaired_check = (output / "evidence" / "repair-check.txt").read_text(
                encoding="utf-8"
            )
            integration_check = (
                output / "evidence" / "integration-check.txt"
            ).read_text(encoding="utf-8")
            self.assertIn("FAILED", bad_check)
            self.assertIn("OK", repaired_check)
            self.assertIn("OK", integration_check)

            dispositions = json.loads(
                (output / "finding-dispositions.json").read_text(encoding="utf-8")
            )
            dispositions_by_id = {
                disposition["finding_id"]: disposition
                for disposition in dispositions
            }
            self.assertEqual({"F1", "F2"}, set(dispositions_by_id))
            self.assertEqual("confirmed", dispositions_by_id["F1"]["status"])
            self.assertEqual("refuted", dispositions_by_id["F2"]["status"])
            self.assertTrue(dispositions_by_id["F1"]["evidence_refs"])
            self.assertTrue(dispositions_by_id["F2"]["evidence_refs"])

            first_verdict = self.read_json(
                output / "critic-round-1" / "verdict.json"
            )
            first_request = self.read_json(
                output / "critic-round-1" / "request.packet.json"
            )
            second_verdict = self.read_json(
                output / "critic-round-2" / "verdict.json"
            )
            self.assertEqual(
                identity["contract_hash"],
                first_request["review_packet"].get("contract_hash"),
            )
            self.assertEqual(
                identity["revision"],
                first_request["review_packet"].get("contract_revision"),
            )
            self.assertEqual("NEEDS_FIXES", first_verdict["verdict"])
            self.assertEqual("PASS", second_verdict["verdict"])

            receipt = self.read_json(output / "final-receipt.json")
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(1, receipt["measured_budget"]["repair_rounds_used"])
            self.assertEqual(0, receipt["measured_budget"]["external_cost_usd"])
            self.assertLessEqual(
                receipt["measured_budget"]["elapsed_seconds"],
                contract["limits"]["elapsed_seconds"],
            )
            self.assertLessEqual(
                receipt["measured_budget"]["source_lines_changed"],
                contract["limits"]["source_lines_changed"],
            )
            self.assertTrue(receipt["claims"])
            self.assertTrue(receipt["evidence_refs"])
            self.assertTrue(receipt["limitations"])
            self.assertEqual([], receipt["unresolved_findings"])
            self.assertEqual([], receipt["human_decisions_required"])
            self.assertNotEqual(
                receipt["result_revision"], receipt["integration_revision"]
            )

    def test_zero_repair_budget_stops_without_applying_the_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture-output"
            result = self.run_fixture(output, repair_round_limit=0)

            self.assertEqual(3, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assertEqual("budget_exhausted", receipt["status"])
            self.assertEqual(0, receipt["measured_budget"]["repair_rounds_used"])
            self.assertNotEqual([], receipt["unresolved_findings"])
            self.assertNotEqual([], receipt["human_decisions_required"])
            self.assertFalse((output / "evidence" / "repair-check.txt").exists())


if __name__ == "__main__":
    unittest.main()
