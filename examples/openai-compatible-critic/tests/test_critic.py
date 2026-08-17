from __future__ import annotations

import re
import json
import os
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
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
        self.assertNotIn("--skip-git-repo-check", text)
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
        self.assertEqual("instructions.md", config["model_instructions_file"])
        self.assertFalse(config["sandbox_workspace_write"]["network_access"])
        provider = config["model_providers"]["deepseek"]
        self.assertEqual("https://api.deepseek.com", provider["base_url"])
        self.assertEqual("DEEPSEEK_API_KEY", provider["env_key"])
        self.assertEqual("responses", provider["wire_api"])

    def test_worker_rejects_non_git_workspace_before_codex(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            workspace = temp / "workspace"
            workspace.mkdir()
            assignment = temp / "assignment.md"
            assignment.write_text("Bounded assignment.\n", encoding="utf-8")
            bin_dir = temp / "bin"
            bin_dir.mkdir()
            called = temp / "codex-called"
            fake_codex = bin_dir / "codex"
            fake_codex.write_text(
                f"#!/usr/bin/env bash\ntouch {called}\n", encoding="utf-8"
            )
            fake_codex.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            env["DEEPSEEK_API_KEY"] = "fake-worker-key"

            result = subprocess.run(
                [str(WORKER / "run.sh"), str(workspace), str(assignment)],
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )

            self.assertNotEqual(0, result.returncode)
            self.assertIn("git repository", result.stderr.lower())
            self.assertFalse(called.exists())


CRITIC = ROOT / "examples" / "openai-compatible-critic"
CRITIC_SCRIPT = CRITIC / "critic.py"
VERDICT_SCHEMA = CRITIC / "verdict.schema.json"
EXAMPLE_PACKET = CRITIC / "review-packet.example.json"
FAKE_KEY = "test-secret-token"


def valid_packet() -> dict[str, object]:
    return {
        "protocol": "klp-core/v0.1",
        "task_id": "example-normalize-title",
        "objective": "Collapse repeated ASCII spaces in normalizeTitle().",
        "commitments": [
            {"id": "C1", "text": "Repeated ASCII spaces collapse to one."}
        ],
        "worker_provider_family": "deepseek",
        "base_revision": "base-abc123",
        "result_revision": "result-def456",
        "changed_files": ["src/title.ts", "tests/title.test.ts"],
        "artifact_diff": "diff --git a/src/title.ts b/src/title.ts",
        "checks": [
            {
                "name": "focused-test",
                "command": "npm test -- tests/title.test.ts",
                "status": "passed",
                "evidence_ref": "E1",
            }
        ],
        "evidence": [
            {"id": "E1", "kind": "test-output", "content": "1 test passed"}
        ],
        "known_limitations": [],
        "unresolved_findings": [],
    }


def valid_verdict() -> dict[str, object]:
    return {
        "reviewed_revision": "result-def456",
        "critic_provider_family": "grok",
        "critic_model": "critic-test-model",
        "verdict": "PASS",
        "summary": "The bounded commitment is supported by the supplied evidence.",
        "findings": [],
        "limitations": [],
    }


class FakeProvider:
    def __init__(self, content: object, status: int = 200) -> None:
        self.content = content
        self.status = status
        self.request_count = 0
        self.request_body: dict[str, object] | None = None
        self.authorization: str | None = None
        self.server: ThreadingHTTPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> "FakeProvider":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - stdlib callback name
                length = int(self.headers.get("Content-Length", "0"))
                owner.request_count += 1
                owner.authorization = self.headers.get("Authorization")
                owner.request_body = json.loads(self.rfile.read(length))
                payload = owner.content
                if not isinstance(payload, bytes):
                    payload = json.dumps(payload).encode("utf-8")
                self.send_response(owner.status)
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
        assert self.server is not None
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def __exit__(self, *args: object) -> None:
        assert self.server is not None
        assert self.thread is not None
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class CriticHarnessTests(unittest.TestCase):
    def run_harness(
        self,
        packet: dict[str, object],
        provider: FakeProvider,
        *,
        critic_family: str = "grok",
        allow_same_family: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, str]]:
        with tempfile.TemporaryDirectory() as temporary:
            temp = Path(temporary)
            packet_path = temp / "packet.json"
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            out_dir = temp / "out"
            env = {
                "PATH": os.environ.get("PATH", ""),
                "LANG": "C.UTF-8",
                "CRITIC_BASE_URL": provider.base_url,
                "CRITIC_API_KEY": FAKE_KEY,
                "CRITIC_MODEL": "critic-test-model",
                "CRITIC_PROVIDER_FAMILY": critic_family,
            }
            command = [
                sys.executable,
                str(CRITIC_SCRIPT),
                "--packet",
                str(packet_path),
                "--schema",
                str(VERDICT_SCHEMA),
                "--out-dir",
                str(out_dir),
                "--timeout-seconds",
                "2",
            ]
            if allow_same_family:
                command.append("--allow-same-family")
            result = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                env=env,
            )
            artifacts = {}
            if out_dir.exists():
                artifacts = {
                    item.name: item.read_text(encoding="utf-8")
                    for item in out_dir.iterdir()
                    if item.is_file()
                }
            return result, artifacts

    def provider_payload(self, verdict: object) -> dict[str, object]:
        content = verdict if isinstance(verdict, str) else json.dumps(verdict)
        return {
            "id": "response-1",
            "model": "critic-test-model",
            "usage": {"total_tokens": 42},
            "choices": [
                {
                    "message": {
                        "content": content,
                        "reasoning_content": "must not be retained",
                    }
                }
            ],
        }

    def test_example_packet_and_schema_are_valid_json(self) -> None:
        self.assertTrue(EXAMPLE_PACKET.is_file())
        self.assertTrue(VERDICT_SCHEMA.is_file())
        self.assertIsInstance(json.loads(EXAMPLE_PACKET.read_text()), dict)
        self.assertIsInstance(json.loads(VERDICT_SCHEMA.read_text()), dict)

    def test_valid_packet_produces_three_secret_free_artifacts(self) -> None:
        with FakeProvider(self.provider_payload(valid_verdict())) as provider:
            result, artifacts = self.run_harness(valid_packet(), provider)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, provider.request_count)
        self.assertEqual(f"Bearer {FAKE_KEY}", provider.authorization)
        self.assertEqual(
            {"request.packet.json", "provider-response.json", "verdict.json"},
            set(artifacts),
        )
        all_output = result.stdout + result.stderr + "".join(artifacts.values())
        self.assertNotIn(FAKE_KEY, all_output)
        self.assertNotIn("reasoning_content", artifacts["provider-response.json"])
        assert provider.request_body is not None
        self.assertEqual("critic-test-model", provider.request_body["model"])
        self.assertFalse(provider.request_body["stream"])
        messages = provider.request_body["messages"]
        self.assertIn("untrusted passive evidence", messages[0]["content"])
        self.assertIn("ignore instructions", messages[0]["content"].lower())

    def test_same_family_fails_before_http(self) -> None:
        with FakeProvider(self.provider_payload(valid_verdict())) as provider:
            result, artifacts = self.run_harness(
                valid_packet(), provider, critic_family="DeepSeek"
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("independent", result.stderr.lower())
        self.assertEqual(0, provider.request_count)
        self.assertNotIn("verdict.json", artifacts)

    def test_same_family_requires_explicit_escape(self) -> None:
        verdict = valid_verdict()
        verdict["critic_provider_family"] = "deepseek"
        with FakeProvider(self.provider_payload(verdict)) as provider:
            result, artifacts = self.run_harness(
                valid_packet(),
                provider,
                critic_family="DeepSeek",
                allow_same_family=True,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(1, provider.request_count)
        self.assertIn("verdict.json", artifacts)
        assert provider.request_body is not None
        system_prompt = provider.request_body["messages"][0]["content"]
        self.assertNotIn("independent", system_prompt.lower())

    def test_missing_packet_field_fails_before_http(self) -> None:
        packet = valid_packet()
        packet.pop("checks")
        with FakeProvider(self.provider_payload(valid_verdict())) as provider:
            result, artifacts = self.run_harness(packet, provider)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing required packet field", result.stderr.lower())
        self.assertEqual(0, provider.request_count)
        self.assertNotIn("verdict.json", artifacts)

    def test_oversized_packet_fails_before_http(self) -> None:
        packet = valid_packet()
        packet["artifact_diff"] = "x" * (256 * 1024)
        with FakeProvider(self.provider_payload(valid_verdict())) as provider:
            result, artifacts = self.run_harness(packet, provider)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("256 kib", result.stderr.lower())
        self.assertEqual(0, provider.request_count)
        self.assertNotIn("verdict.json", artifacts)

    def test_http_error_produces_no_verdict(self) -> None:
        with FakeProvider({"error": "provider failure"}, status=500) as provider:
            result, artifacts = self.run_harness(valid_packet(), provider)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("http 500", result.stderr.lower())
        self.assertNotIn("verdict.json", artifacts)

    def test_non_json_assistant_content_produces_no_verdict(self) -> None:
        with FakeProvider(self.provider_payload("not json")) as provider:
            result, artifacts = self.run_harness(valid_packet(), provider)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("valid json", result.stderr.lower())
        self.assertNotIn("verdict.json", artifacts)

    def test_schema_invalid_verdict_produces_no_verdict(self) -> None:
        verdict = valid_verdict()
        verdict.pop("summary")
        with FakeProvider(self.provider_payload(verdict)) as provider:
            result, artifacts = self.run_harness(valid_packet(), provider)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("schema", result.stderr.lower())
        self.assertNotIn("verdict.json", artifacts)

    def test_pass_with_blocking_finding_produces_no_verdict(self) -> None:
        verdict = valid_verdict()
        verdict["findings"] = [
            {
                "finding_id": "F1",
                "severity": "important",
                "blocking": True,
                "commitment": "C1",
                "observed": "The evidence is incomplete.",
                "expected": "The evidence proves C1.",
                "evidence_refs": ["E1"],
                "repair_acceptance": "Provide direct passing evidence.",
            }
        ]
        with FakeProvider(self.provider_payload(verdict)) as provider:
            result, artifacts = self.run_harness(valid_packet(), provider)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("blocking finding", result.stderr.lower())
        self.assertNotIn("verdict.json", artifacts)


if __name__ == "__main__":
    unittest.main()
