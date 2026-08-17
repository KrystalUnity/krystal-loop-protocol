from __future__ import annotations

import re
import subprocess
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
WORKER = ROOT / "examples" / "deepseek-codex-worker"
WORKER_FILES = (
    "README.md",
    "config.toml.example",
    "instructions.md",
    "run.sh",
    "assignment.example.md",
    "expected-handover.json",
)


class WorkerExampleTests(unittest.TestCase):
    def test_worker_assets_exist(self) -> None:
        missing = [name for name in WORKER_FILES if not (WORKER / name).is_file()]
        self.assertEqual([], missing)

    def test_worker_launcher_is_portable_and_contained(self) -> None:
        launcher = WORKER / "run.sh"
        if not launcher.exists():
            self.skipTest("worker launcher not implemented")

        text = launcher.read_text(encoding="utf-8")
        private_absolute_path = re.compile(
            r"(?m)(?:^|[=\"'[:space:]])/(?:root|home|var)/"
        )
        self.assertIsNone(private_absolute_path.search(text))
        self.assertNotIn(".env", text)
        self.assertNotIn("git ", text.lower())
        self.assertIn("--ephemeral", text)
        self.assertRegex(text, r'"\$codex_bin"\s+exec\b')

        result = subprocess.run(
            ["bash", "-n", str(launcher)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(0, result.returncode, result.stderr)

    def test_worker_config_has_bounded_deepseek_profile(self) -> None:
        config_path = WORKER / "config.toml.example"
        if not config_path.exists():
            self.skipTest("worker configuration not implemented")

        with config_path.open("rb") as handle:
            config = tomllib.load(handle)

        self.assertEqual("deepseek", config["model_provider"])
        self.assertEqual("deepseek-v4-flash", config["model"])
        self.assertEqual("never", config["approval_policy"])
        self.assertEqual("workspace-write", config["sandbox_mode"])
        self.assertFalse(config["sandbox_workspace_write"]["network_access"])
        provider = config["model_providers"]["deepseek"]
        self.assertEqual("https://api.deepseek.com", provider["base_url"])
        self.assertEqual("DEEPSEEK_API_KEY", provider["env_key"])
        self.assertEqual("responses", provider["wire_api"])


if __name__ == "__main__":
    unittest.main()
