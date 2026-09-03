from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V03DocumentationTests(unittest.TestCase):
    def text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_normative_protocol_contains_capability_gate(self) -> None:
        protocol = self.text("PROTOCOL.md")
        for required in (
            "Version: 0.3 draft",
            "## Mission Contract",
            "mission_binding_check",
            "capability_baseline",
            "capability_check",
            "mission_mismatch",
            "capability_regression",
            "capability_unproven",
            "mission_amendment_requested",
            "plain-English Operator Impact Statement",
        ):
            self.assertIn(required, protocol)

    def test_agent_guide_requires_mission_recovery_fields(self) -> None:
        guide = self.text("AI_AGENT_INTEGRATION.md")
        for required in (
            "mission_id",
            "mission_revision",
            "mission_hash",
            "affected_capabilities[]",
            "capability_commitments[]",
            "expected_capability_delta",
            "required_capability_probes[]",
            "capability_report",
        ):
            self.assertIn(required, guide)

    def test_probe_targets_are_artifact_specific(self) -> None:
        for relative in ("PROTOCOL.md", "AI_AGENT_INTEGRATION.md"):
            document = " ".join(self.text(relative).split())
            self.assertIn(
                "pre-work required probes run against the accepted baseline artifact",
                document,
            )
            self.assertIn(
                "post-integration required probes run against the exact integrated "
                "artifact revision",
                document,
            )

    def test_baseline_failure_is_not_capability_regression(self) -> None:
        for relative in ("PROTOCOL.md", "AI_AGENT_INTEGRATION.md"):
            document = " ".join(self.text(relative).split())
            self.assertIn(
                "absent, stale, inconclusive, failed, or otherwise unusable pre-work "
                "baseline",
                document,
            )
            self.assertIn(
                "`capability_regression` is reserved for post-integration evidence "
                "that falls below the frozen accepted baseline",
                document,
            )

    def test_capability_unproven_precedes_generic_blocked(self) -> None:
        for relative in ("PROTOCOL.md", "AI_AGENT_INTEGRATION.md"):
            document = " ".join(self.text(relative).split())
            self.assertIn(
                "`capability_unproven` takes precedence over the generic `blocked` state",
                document,
            )

    def test_stop_list_qualifies_post_integration_regression(self) -> None:
        guide = " ".join(self.text("AI_AGENT_INTEGRATION.md").split())
        stop_behavior = guide.split("## Stop Behavior", 1)[1].split(
            "## Integration Checklist", 1
        )[0]
        self.assertNotIn(
            "a capability probe fails: `capability_regression`",
            stop_behavior,
        )
        self.assertIn(
            "a post-integration capability probe fails by falling below the frozen "
            "accepted baseline: `capability_regression`",
            stop_behavior,
        )

    def test_public_and_runtime_guidance_links_the_capability_fixture(self) -> None:
        readme = self.text("README.md")
        prompt_section = readme.split("## Start With One Prompt", 1)[1].split(
            "## Run a Worker and Critic", 1
        )[0]
        starter_prompt = prompt_section.split("```text", 1)[1].split("```", 1)[0]
        runtime = self.text("RUNTIME_PROFILES.md")
        safety = self.text("SAFETY_AND_LIMITS.md")
        hermes = self.text("adapters/hermes-kanban.md")
        fixture = ROOT / "examples" / "capability-regression" / "README.md"
        self.assertTrue(fixture.is_file())
        self.assertIn("examples/fail-review-repair/README.md", starter_prompt)
        self.assertIn("examples/capability-regression/README.md", starter_prompt)
        self.assertIn("Capability Auditor", runtime)
        self.assertIn("capability_unproven", safety)
        self.assertIn("Mission Custodian", hermes)
        self.assertIn("Execution Coordinator", hermes)

    def test_all_local_markdown_links_resolve(self) -> None:
        documents = (
            "README.md",
            "PROTOCOL.md",
            "AI_AGENT_INTEGRATION.md",
            "RUNTIME_PROFILES.md",
            "SAFETY_AND_LIMITS.md",
            "adapters/hermes-kanban.md",
            "examples/capability-regression/README.md",
        )
        pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
        for relative in documents:
            source = ROOT / relative
            for match in pattern.findall(source.read_text(encoding="utf-8")):
                target = match.split("#", 1)[0]
                if not target or "://" in target or target.startswith("mailto:"):
                    continue
                resolved = (source.parent / target).resolve()
                with self.subTest(source=relative, target=target):
                    self.assertTrue(resolved.exists(), str(resolved))


if __name__ == "__main__":
    unittest.main()
