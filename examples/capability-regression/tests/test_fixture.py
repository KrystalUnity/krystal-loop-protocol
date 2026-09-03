from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "examples" / "capability-regression" / "run_fixture.py"


class CapabilityRegressionFixtureTests(unittest.TestCase):
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
            self.assertEqual("klp-core/v0.3", receipt["protocol"])
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(
                "preserved",
                receipt["capability_report"]["adaptive-choice"]["disposition"],
            )
            self.assertEqual(
                1, receipt["measured_budget"]["repair_rounds_used"]
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


if __name__ == "__main__":
    unittest.main()
