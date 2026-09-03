from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "examples" / "capability-regression" / "run_fixture.py"


class CapabilityRegressionFixtureTests(unittest.TestCase):
    RECEIPT_KEYS = {
        "protocol",
        "status",
        "mission_identity",
        "contract_identity",
        "result_revision",
        "integration_revision",
        "claims",
        "evidence_refs",
        "capability_report",
        "measured_budget",
        "limitations",
        "unresolved_findings",
        "human_decisions_required",
        "state_ledger_tail_hash",
    }

    def run_fixture(
        self, output: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(FIXTURE), "--out-dir", str(output), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
        )

    def read_json(self, path: Path) -> dict[str, object]:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def read_states(self, path: Path) -> list[str]:
        return [
            json.loads(line)["new_state"]
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def assert_terminal_state(self, output: Path, expected: str) -> list[str]:
        states = self.read_states(output / "state-events.jsonl")
        self.assertEqual(expected, states[-1])
        self.assertEqual(1, states.count(expected))
        self.assertNotIn("completed", states)
        return states

    def assert_complete_receipt(self, receipt: dict[str, object]) -> None:
        self.assertEqual(self.RECEIPT_KEYS, set(receipt))
        self.assertEqual("klp-core/v0.3", receipt["protocol"])
        self.assertIsInstance(receipt["mission_identity"], dict)
        self.assertIsInstance(receipt["contract_identity"], dict)
        self.assertTrue(receipt["claims"])
        self.assertTrue(receipt["evidence_refs"])
        self.assertIsInstance(receipt["capability_report"], dict)
        self.assertEqual(
            {"repair_rounds_used", "elapsed_seconds", "external_cost_usd"},
            set(receipt["measured_budget"]),
        )
        self.assertTrue(receipt["limitations"])
        self.assertIsInstance(receipt["unresolved_findings"], list)
        self.assertIsInstance(receipt["human_decisions_required"], list)
        self.assertIsInstance(receipt["state_ledger_tail_hash"], str)

    @contextmanager
    def fixture_output(self, *arguments: str):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture-output"
            yield self.run_fixture(output, *arguments), output

    def test_green_task_checks_cannot_hide_capability_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture-output"
            result = self.run_fixture(output)

            self.assertEqual(0, result.returncode, result.stderr)
            states = self.read_states(output / "state-events.jsonl")
            self.assertIn("capability_regression", states)
            self.assertLess(
                states.index("capability_regression"), states.index("completed")
            )

            worker_check = (output / "evidence" / "worker-check.txt").read_text()
            failed_capability = self.read_json(
                output / "evidence" / "capability-after-integration-1.json"
            )
            repaired_capability = self.read_json(
                output / "evidence" / "capability-after-integration-2.json"
            )
            self.assertIn("OK", worker_check)
            restriction = self.read_json(
                output / "evidence" / "restriction-candidate.json"
            )
            self.assertEqual(
                "replace-adaptive-with-fixed-sequence",
                restriction["change_kind"],
            )
            self.assertEqual(
                ["adaptive-choice"], restriction["affected_capabilities"]
            )
            disposition = self.read_json(
                output / "evidence" / "restriction-disposition-2.json"
            )
            self.assertEqual("cleared", disposition["status"])
            self.assertIn(
                "evidence/capability-after-integration-2.json",
                disposition["evidence_refs"],
            )
            binding = self.read_json(output / "mission-binding-report.json")
            self.assertEqual("mission-custodian", binding["actor"])
            self.assertNotEqual(
                binding["actor"], binding["execution_coordinator"]
            )
            self.assertEqual("failed", failed_capability["result"])
            self.assertEqual(
                "capability-auditor", failed_capability["auditor_identity"]
            )
            self.assertEqual("passed", repaired_capability["result"])

            receipt = self.read_json(output / "final-receipt.json")
            self.assert_complete_receipt(receipt)
            self.assertEqual("klp-core/v0.3", receipt["protocol"])
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(
                "preserved",
                receipt["capability_report"]["adaptive-choice"]["disposition"],
            )
            self.assertEqual(
                1, receipt["measured_budget"]["repair_rounds_used"]
            )
            self.assertEqual(
                receipt["result_revision"],
                self.read_json(output / "critic-round-2" / "verdict.json")[
                    "reviewed_revision"
                ],
            )
            self.assertNotEqual(
                receipt["result_revision"], receipt["integration_revision"]
            )
            self.assertEqual([], receipt["unresolved_findings"])
            self.assertEqual([], receipt["human_decisions_required"])
            self.assertIn("critic-round-2/verdict.json", receipt["evidence_refs"])
            self.assertIn("evidence/repair-check.txt", receipt["evidence_refs"])

            task_snapshot = self.read_json(output / "task.snapshot.json")
            task = task_snapshot["task"]
            self.assertEqual(1, task["limits"]["repair_rounds"])
            self.assertIn("coordinator_may", task["delegation"])
            self.assertIn("must_escalate", task["delegation"])
            self.assertLessEqual(
                receipt["measured_budget"]["elapsed_seconds"],
                task["limits"]["elapsed_seconds"],
            )
            self.assertLessEqual(
                receipt["measured_budget"]["external_cost_usd"],
                task["limits"]["external_cost_usd"],
            )
            for evidence in (failed_capability, repaired_capability):
                self.assertEqual(
                    task["mission_hash"], evidence["mission_hash"]
                )
                self.assertEqual(
                    evidence["expected_artifact_revision"],
                    evidence["artifact_revision"],
                )

            workspace = output / "workspace"
            workspace_status = subprocess.run(
                ["git", "status", "--short", "--untracked-files=all"],
                cwd=workspace,
                check=False,
                capture_output=True,
                text=True,
                env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
            )
            generated_bytecode = sorted(
                str(path.relative_to(workspace))
                for path in workspace.rglob("*")
                if path.name == "__pycache__" or path.suffix == ".pyc"
            )
            self.assertEqual(
                (0, "", []),
                (
                    workspace_status.returncode,
                    workspace_status.stdout,
                    generated_bytecode,
                ),
                workspace_status.stderr,
            )

    def test_zero_repair_budget_stops_after_capability_regression(self) -> None:
        with self.fixture_output("--repair-round-limit", "0") as (result, output):
            self.assertEqual(3, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assert_complete_receipt(receipt)
            self.assertEqual("budget_exhausted", receipt["status"])
            self.assertEqual(
                "degraded",
                receipt["capability_report"]["adaptive-choice"]["disposition"],
            )
            self.assert_terminal_state(output, "budget_exhausted")
            self.assertFalse(
                (
                    output
                    / "evidence"
                    / "capability-after-integration-2.json"
                ).exists()
            )

    def test_inconclusive_probe_cannot_complete(self) -> None:
        with self.fixture_output("--probe-mode", "inconclusive") as (result, output):
            self.assertEqual(4, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assert_complete_receipt(receipt)
            self.assertEqual("capability_unproven", receipt["status"])
            states = self.assert_terminal_state(output, "capability_unproven")
            self.assertEqual(1, states.count("building"))
            self.assertNotIn("capability_regression", states)
            self.assertFalse(
                (
                    output
                    / "evidence"
                    / "capability-after-integration-2.json"
                ).exists()
            )
            self.assertFalse((output / "evidence" / "repair-check.txt").exists())
            self.assertFalse(
                (output / "evidence" / "restriction-disposition-2.json").exists()
            )

    def test_undeclared_trigger_stops_before_worker_execution(self) -> None:
        with self.fixture_output("--omit-capability-declaration") as (result, output):
            self.assertEqual(5, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assert_complete_receipt(receipt)
            self.assertEqual("mission_mismatch", receipt["status"])
            capability = receipt["capability_report"]["adaptive-choice"]
            self.assertEqual("unproven", capability["disposition"])
            self.assertEqual(
                "triggered capability not declared: adaptive-choice",
                capability["reason"],
            )
            self.assert_terminal_state(output, "mission_mismatch")
            self.assertFalse((output / "evidence" / "worker-check.txt").exists())

    def test_nonpassing_baseline_stops_before_worker_execution(self) -> None:
        for mode in ("failed", "inconclusive"):
            with self.subTest(mode=mode):
                with self.fixture_output("--baseline-probe-mode", mode) as (
                    result,
                    output,
                ):
                    self.assertEqual(4, result.returncode, result.stderr)
                    receipt = self.read_json(output / "final-receipt.json")
                    self.assert_complete_receipt(receipt)
                    self.assertEqual("capability_unproven", receipt["status"])
                    self.assertEqual(
                        "unproven",
                        receipt["capability_report"]["adaptive-choice"][
                            "disposition"
                        ],
                    )
                    states = self.assert_terminal_state(
                        output, "capability_unproven"
                    )
                    self.assertNotIn("assigned", states)
                    self.assertNotIn("building", states)
                    self.assertFalse(
                        (output / "evidence" / "worker-check.txt").exists()
                    )

    def test_mismatched_expected_artifact_revision_is_unproven(self) -> None:
        with self.fixture_output("--mismatch-baseline-artifact-revision") as (
            result,
            output,
        ):
            self.assertEqual(4, result.returncode, result.stderr)
            evidence = self.read_json(
                output / "evidence" / "capability-baseline.json"
            )
            self.assertEqual("inconclusive", evidence["result"])
            self.assertNotEqual(
                evidence["expected_artifact_revision"],
                evidence["artifact_revision"],
            )
            self.assertIn("artifact revision", evidence["identity_error"])
            receipt = self.read_json(output / "final-receipt.json")
            self.assert_complete_receipt(receipt)
            self.assertEqual("capability_unproven", receipt["status"])
            self.assertFalse((output / "evidence" / "worker-check.txt").exists())

    def test_cli_cannot_increase_frozen_repair_limit(self) -> None:
        with self.fixture_output("--repair-round-limit", "2") as (result, output):
            self.assertEqual(2, result.returncode)
            self.assertIn("cannot increase", result.stderr)
            self.assertFalse((output / "final-receipt.json").exists())


if __name__ == "__main__":
    unittest.main()
