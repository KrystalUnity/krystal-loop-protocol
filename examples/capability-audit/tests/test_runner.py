from __future__ import annotations

import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


RUNNER = Path(__file__).resolve().parents[1] / "runner.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AuditRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        (self.repo / "value.txt").write_text("old")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD")
        (self.repo / "value.txt").write_text("new")
        self.git("commit", "-qam", "candidate")
        self.candidate = self.git("rev-parse", "HEAD")
        (self.repo / "value.txt").write_text("operator dirty file")
        (self.repo / "untracked.txt").write_text("keep")
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        for name in ("mission.md", "task.md"):
            (self.inputs / name).write_text("Frozen fixture contract: " + name)
        self.probe = self.inputs / "probe.py"
        self.probe.write_text(
            "import json\nfrom pathlib import Path\n"
            "value = Path('/work/value.txt').read_text()\n"
            "Path('/results/observations.json').write_text(json.dumps({'value':value}))\n"
            "print('observed', value)\n"
        )
        self.manifest = {
            "schema": "klp-capability-audit/v1",
            "contracts": {
                name: {"path": name + ".md", "sha256": sha(self.inputs / (name + ".md"))}
                for name in ("mission", "task")
            },
            "instruments": [{"path": "probe.py", "sha256": sha(self.probe)}],
            "limits": {"elapsed_seconds": 15, "max_log_bytes": 65536},
            "probes": [{
                "id": "value", "capability_ids": ["value-behavior"],
                "argv": ["python3", "/instruments/probe.py"],
                "timeout_seconds": 3, "ports": [],
                "expect": {
                    "base": {"exit_code": 0, "observations": {"value": "old"}},
                    "candidate": {"exit_code": 0, "observations": {"value": "new"}},
                },
            }],
        }
        self.output = self.root / "evidence"

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True).strip()

    def run_audit(self, *, env=None, revision=None):
        self.assertTrue(RUNNER.is_file(), "capability audit runner is not implemented")
        self.manifest["instruments"][0]["sha256"] = sha(self.probe)
        manifest_path = self.inputs / "manifest.json"
        manifest_path.write_text(json.dumps(self.manifest))
        return subprocess.run(
            [sys.executable, str(RUNNER), "run", "--repo", str(self.repo),
             "--base", self.base, "--candidate", revision or self.candidate,
             "--manifest", str(manifest_path), "--manifest-sha256", sha(manifest_path),
             "--out-dir", str(self.output)],
            capture_output=True, text=True, env=env, timeout=30,
        )

    def report(self):
        return json.loads((self.output / "comparison.json").read_text())

    def test_exact_snapshots_compact_packet_and_dirty_checkout_preserved(self):
        before = self.git("status", "--porcelain")
        result = self.run_audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = self.report()
        self.assertTrue(report["all_expectations_met"])
        self.assertEqual(report["candidate_revision"], self.candidate)
        rows = report["probes"][0]
        self.assertEqual(rows["base"]["observations"], {"value": "old"})
        self.assertEqual(rows["candidate"]["observations"], {"value": "new"})
        self.assertEqual(report["runner_sha256"], sha(RUNNER))
        self.assertEqual(before, self.git("status", "--porcelain"))
        self.assertEqual((self.repo / "value.txt").read_text(), "operator dirty file")
        packet = json.loads((self.output / "judge-packet.json").read_text())
        self.assertIn("Frozen fixture contract", packet["contracts"]["mission"])
        self.assertIn("-old", packet["artifact_diff"])
        self.assertFalse(packet["authorizes_acceptance"])
        self.assertEqual(packet["comparison"], report)
        ledger = [json.loads(line) for line in (self.output / "commands.jsonl").read_text().splitlines()]
        self.assertEqual([x["event"] for x in ledger], ["started", "finished"] * 2)
        self.assertEqual([x["side"] for x in ledger], ["base", "base", "candidate", "candidate"])
        self.assertIn("observed old", (self.output / "logs/value-base.stdout").read_text())

    def test_exit_zero_without_observations_is_not_a_pass(self):
        self.probe.write_text("print('PASS')")
        self.assertEqual(self.run_audit().returncode, 1)
        self.assertEqual(self.report()["probes"][0]["base"]["status"], "unproven")

    def test_invalid_observations_are_retained_for_review(self):
        self.probe.write_text("from pathlib import Path\nPath('/results/observations.json').write_text('not JSON')")
        self.assertEqual(self.run_audit().returncode, 1)
        self.assertEqual(self.report()["probes"][0]["base"]["status"], "unproven")
        self.assertTrue((self.output / "logs/value-base.observations.json").is_file())
        self.assertEqual((self.output / "logs/value-base.observations.json").read_text(), "not JSON")

    def test_missing_required_control_is_unproven(self):
        self.manifest["probes"][0]["expect"]["base"]["observations"]["negative_control"] = True
        self.assertEqual(self.run_audit().returncode, 1)
        self.assertEqual(self.report()["probes"][0]["base"]["status"], "unproven")

    def test_duplicate_probe_id_is_rejected_before_execution(self):
        self.manifest["probes"].append(dict(self.manifest["probes"][0]))
        self.assertEqual(self.run_audit().returncode, 2)
        self.assertFalse((self.output / "commands.jsonl").exists())

    def test_exhausted_budget_records_not_run_instead_of_skipping_silently(self):
        self.manifest["limits"]["elapsed_seconds"] = 0.000001
        self.assertEqual(self.run_audit().returncode, 1)
        for side in ("base", "candidate"):
            self.assertEqual(self.report()["probes"][0][side]["execution_status"], "not_run")

    def test_export_ignore_cannot_hide_committed_source(self):
        (self.repo / ".gitattributes").write_text("value.txt export-ignore\n")
        self.git("add", ".gitattributes")
        self.git("commit", "-qm", "attribute hides source")
        self.assertEqual(self.run_audit(revision=self.git("rev-parse", "HEAD")).returncode, 2)

    def test_git_tar_umask_cannot_hide_executable_bit_regression(self):
        (self.repo / "value.txt").write_text("new")
        (self.repo / "value.txt").chmod(0o755)
        self.git("add", "value.txt")
        self.git("commit", "-qm", "mode change")
        self.git("config", "tar.umask", "0111")
        self.probe.write_text(
            "import json, stat\nfrom pathlib import Path\n"
            "executable=bool(Path('/work/value.txt').stat().st_mode & stat.S_IXUSR)\n"
            "Path('/results/observations.json').write_text(json.dumps({'executable':executable}))\n"
        )
        for side in ("base", "candidate"):
            self.manifest["probes"][0]["expect"][side]["observations"] = {"executable": False}
        self.assertEqual(self.run_audit(revision=self.git("rev-parse", "HEAD")).returncode, 1)
        row = self.report()["probes"][0]
        self.assertEqual(row["base"]["status"], "matched")
        self.assertEqual(row["candidate"]["status"], "mismatch")
        self.assertEqual(row["candidate"]["observations"], {"executable": True})

    def test_mismatched_control_is_retained(self):
        self.manifest["probes"][0]["expect"]["candidate"]["observations"]["value"] = "wrong"
        self.assertEqual(self.run_audit().returncode, 1)
        row = self.report()["probes"][0]["candidate"]
        self.assertEqual(row["status"], "mismatch")
        self.assertEqual(row["observations"]["value"], "new")

    def test_missing_control_and_boolean_number_confusion_do_not_pass(self):
        self.probe.write_text("from pathlib import Path\nPath('/results/observations.json').write_text('{\"check\": 1}')")
        for side in ("base", "candidate"):
            self.manifest["probes"][0]["expect"][side]["observations"] = {"check": True}
        self.assertEqual(self.run_audit().returncode, 1)
        self.assertEqual(self.report()["probes"][0]["base"]["status"], "mismatch")

    def test_expected_baseline_failure_does_not_become_acceptance(self):
        self.probe.write_text(self.probe.read_text() + "raise SystemExit(1 if value == 'old' else 0)\n")
        self.manifest["probes"][0]["expect"]["base"]["exit_code"] = 1
        self.assertEqual(self.run_audit().returncode, 0)
        self.assertEqual(self.report()["probes"][0]["base"]["exit_code"], 1)
        self.assertNotIn("capability_report", self.report())

    def test_timeout_is_unproven_even_after_writing_valid_json(self):
        self.probe.write_text(self.probe.read_text() + "import time\ntime.sleep(5)\n")
        self.manifest["probes"][0]["timeout_seconds"] = 0.1
        self.assertEqual(self.run_audit().returncode, 1)
        self.assertEqual(self.report()["probes"][0]["base"]["execution_status"], "timeout")

    def test_output_limit_is_unproven(self):
        self.probe.write_text(self.probe.read_text() + "print('x' * 1000000)\n")
        self.manifest["limits"]["max_log_bytes"] = 1024
        self.assertEqual(self.run_audit().returncode, 1)
        self.assertEqual(self.report()["probes"][0]["base"]["execution_status"], "output_limit")
        self.assertLessEqual((self.output / "logs/value-base.stdout").stat().st_size, 1024)

    def test_contract_hash_mismatch_stops_before_execution(self):
        self.manifest["contracts"]["mission"]["sha256"] = "0" * 64
        self.assertEqual(self.run_audit().returncode, 2)
        self.assertFalse((self.output / "commands.jsonl").exists())

    def test_revision_must_be_an_exact_commit(self):
        self.assertEqual(self.run_audit(revision="HEAD").returncode, 2)

    def test_path_escape_is_rejected(self):
        self.manifest["instruments"][0]["path"] = "../outside.py"
        self.assertEqual(self.run_audit().returncode, 2)

    def test_no_provider_environment_host_files_or_host_network(self):
        listener = socket.socket()
        self.addCleanup(listener.close)
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        canary = self.root / "host-only"
        canary.write_text("must not be visible")
        self.probe.write_text(
            "import json, os, socket\nfrom pathlib import Path\n"
            f"s=socket.socket(); s.settimeout(0.2)\nnetwork=s.connect_ex(('127.0.0.1',{port})) != 0\n"
            f"checks={{'no_key': 'OPENAI_API_KEY' not in os.environ, 'no_custom': 'KU_SECRET_TEST' not in os.environ, 'host_hidden': not Path({str(canary)!r}).exists(), 'network_denied': network}}\n"
            "Path('/results/observations.json').write_text(json.dumps(checks))\n"
        )
        checks = dict.fromkeys(("no_key", "no_custom", "host_hidden", "network_denied"), True)
        for side in ("base", "candidate"):
            self.manifest["probes"][0]["expect"][side]["observations"] = checks
        result = self.run_audit(env={**os.environ, "OPENAI_API_KEY": "fake-fixture-only", "KU_SECRET_TEST": "fake"})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_probe_workspaces_are_fresh(self):
        self.probe.write_text(self.probe.read_text() + "Path('/work/value.txt').write_text('modified by test')\n")
        second = json.loads(json.dumps(self.manifest["probes"][0]))
        second["id"] = "second"
        self.manifest["probes"].append(second)
        self.assertEqual(self.run_audit().returncode, 0)
        self.assertEqual(len(self.report()["probes"]), 2)

    def test_declared_ports_and_side_specific_arguments(self):
        self.probe.write_text(self.probe.read_text() + "import sys\nassert sys.argv[1] == value\n")
        self.manifest["probes"][0]["side_args"] = {"base": ["old"], "candidate": ["new"]}
        self.manifest["probes"][0]["ports"] = [32101]
        self.assertEqual(self.run_audit().returncode, 0)

    def test_verification_detects_tampered_logs(self):
        run = self.run_audit()
        self.assertEqual(run.returncode, 0, run.stderr)
        root_hash = sha(self.output / "evidence-manifest.json")
        command = [sys.executable, str(RUNNER), "verify", "--out-dir", str(self.output), "--evidence-sha256", root_hash]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 0)
        (self.output / "logs/value-base.stdout").write_text("tampered")
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)

    def test_existing_evidence_is_never_overwritten(self):
        self.output.mkdir()
        (self.output / "keep").write_text("retain")
        self.assertEqual(self.run_audit().returncode, 2)
        self.assertEqual((self.output / "keep").read_text(), "retain")


if __name__ == "__main__":
    unittest.main()
