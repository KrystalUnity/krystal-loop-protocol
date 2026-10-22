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
            "Version: 0.3.2 draft",
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

    def test_demonstrated_failure_rule_is_bounded_and_has_size_example(self) -> None:
        protocol = " ".join(self.text("PROTOCOL.md").split())
        for required in (
            "within supported operating conditions",
            "blocks acceptance, even if production has not encountered it",
            "proximity to a limit without evidence of crossing it",
            "repair outside delegation still requires",
            "hypothetical example, not a verified production incident",
            "actual serialized bytes measured at the enforcing boundary",
            "77 KiB result against a 131 KiB ceiling does not alone demonstrate failure",
            "154 KiB before envelope overhead",
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
            "EXECUTION_PROFILES.md",
            "examples/standard-task.md",
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

    def test_execution_profiles_preserve_critical_identity_and_escalation(self) -> None:
        profiles = " ".join(self.text("EXECUTION_PROFILES.md").split())
        for required in (
            "klp-standard/v0.1", "klp-core/v0.3",
            "not a claim of Core v0.3 conformance",
            "Never downgrade an active Critical run",
            "Unknown impact is not evidence of low risk",
            "save/schema migration", "security or authorization boundary",
            "economy", "Release qualification", "accepted baseline",
        ):
            self.assertIn(required, profiles)

    def test_standard_record_is_compact_but_retains_authority_and_proof(self) -> None:
        template = self.text("examples/standard-task.md")
        for required in (
            "klp-standard/v0.1", "authority_ref", "product_promise_ref",
            "profile_reason", "base_revision", "result_revision",
            "protected_paths", "adjacent_edit_allowance", "reviewer_identity",
            "blocking", "evidence_refs", "limitations", "human_decisions_required",
            "time_limit", "cost_limit", "repair_limit",
        ):
            self.assertIn(required, template)

    def test_profile_guidance_is_reachable_without_new_runtime_requirements(self) -> None:
        for relative in ("README.md", "PROTOCOL.md", "AI_AGENT_INTEGRATION.md",
                         "RUNTIME_PROFILES.md"):
            self.assertIn("EXECUTION_PROFILES.md", self.text(relative))
        profiles = " ".join(self.text("EXECUTION_PROFILES.md").split())
        for required in ("No per-step message", "one independent critic pass",
                         "Do not build a stamping tool", "required check that did not run"):
            self.assertIn(required, profiles)

    def test_review_guidance_rejects_invented_requirements_and_long_timeout_default(self) -> None:
        guide = " ".join(self.text("AI_AGENT_INTEGRATION.md").split())
        for required in ("whole touched functions", "necessary callers",
                         "not a blanket 800-second default", "sim hash",
                         "not a new acceptance condition"):
            self.assertIn(required, guide)

    def test_offline_safety_and_adjacent_edit_authority_are_explicit(self) -> None:
        safety = " ".join(self.text("SAFETY_AND_LIMITS.md").split())
        for required in ("allowlisted environment", "Deny external network access",
                         "pre-authorized adjacent-edit allowance", "missing assertion"):
            self.assertIn(required, safety)


if __name__ == "__main__":
    unittest.main()
