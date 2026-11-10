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
            "Version: 0.3.3 draft",
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
        guide = self.text("docs/your-own-agents.md")
        self.assertIn("docs/your-own-agents.md", self.text("README.md"))
        prompt_section = guide.split("## Start With One Prompt", 1)[1].split(
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
        # Every page a reader or an agent can land on, and the index written for language models.
        documents = sorted(
            str(path.relative_to(ROOT)) for path in list(ROOT.rglob("*.md")) + [ROOT / "llms.txt"]
            if ".git" not in path.parts and "design-notes" not in path.parts and "receipts" not in path.parts
        )
        self.assertIn("BENCHMARKS.md", documents)
        self.assertIn("docs/how-it-works.md", documents)
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
            "economy", "release bundle", "accepted baseline",
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

    def test_standard_critic_confirms_profile_without_an_extra_review_round(self) -> None:
        profiles = " ".join(self.text("EXECUTION_PROFILES.md").split())
        for required in (
            "same critic pass", "exact candidate", "profile_assessment",
            "eligible", "critical_trigger", "insufficient_evidence",
            "Missing or unresolved profile assessment blocks Standard acceptance",
        ):
            self.assertIn(required, profiles)
        template = self.text("examples/standard-task.md")
        self.assertIn("profile_assessment", template)
        self.assertIn("project_policy_ref", template)

    def test_routine_release_keeps_artifact_proof_and_operator_authority(self) -> None:
        profiles = " ".join(self.text("EXECUTION_PROFILES.md").split())
        for required in (
            "## Routine Release Gate", "does not automatically make it Critical",
            "entire release bundle", "exact release artifact",
            "post-release checks", "rollback", "operator authorization",
            "gate is not deployment authority", "Existing Critical runs retain",
        ):
            self.assertIn(required, profiles)
        self.assertNotIn(
            "Release qualification, deployment, production mutation or live activation.",
            profiles,
        )
        for relative in ("README.md", "PROTOCOL.md", "AI_AGENT_INTEGRATION.md",
                         "SAFETY_AND_LIMITS.md", "examples/standard-task.md"):
            self.assertIn("routine-release-gate", self.text(relative))

    def test_economy_policy_cannot_exempt_persistent_or_protected_effects(self) -> None:
        profiles = " ".join(self.text("EXECUTION_PROFILES.md").split())
        for required in (
            "operator-approved, versioned project policy",
            "Persistent currency, purchases, saves and account progression remain Critical",
            "indirect persistent effects", "Temporary in-run tuning",
            "cannot override a Mission Contract trigger",
        ):
            self.assertIn(required, profiles)

    def test_behavior_triggers_do_not_silently_narrow_existing_missions(self) -> None:
        for relative in ("PROTOCOL.md", "EXECUTION_PROFILES.md"):
            document = " ".join(self.text(relative).split())
            self.assertIn("whole-file trigger", document)
            self.assertIn("Mission Amendment Request", document)
        profiles = " ".join(self.text("EXECUTION_PROFILES.md").split())
        for required in (
            "Prefer protected behavior or claims over whole-file triggers",
            "Never use a path mismatch as proof that behavior is safe",
            "An existing whole-file trigger remains binding",
            "plain-English impact statement",
        ):
            self.assertIn(required, profiles)

    def test_machine_readable_evidence_matches_the_benchmark_receipts(self) -> None:
        import json
        evidence = json.loads(self.text("evidence.json"))
        report = json.loads(self.text("case-studies/feature-benchmark-2026-11-10/report.json"))
        published = {row["arm"]: row for row in report["arms"].values()}
        bench = next(r for r in evidence["results"] if r["id"] == "feature-benchmark-2026-11-10")
        for row in bench["arms"]:
            self.assertEqual(row["solved"], published[row["arm"]]["solved"], row["label"])
            self.assertAlmostEqual(row["usd_total"], float(published[row["arm"]]["usd"]), places=2, msg=row["label"])
        reviews = report["reviews"]
        for row in bench["arms"]:
            if row["arm"] in reviews:
                self.assertEqual(row["review"]["findings_confirmed_by_probe"], reviews[row["arm"]]["findings"]["confirmed"])
                self.assertEqual(row["review"]["findings_fixed_and_verified"], reviews[row["arm"]]["findings_closed"])
                self.assertEqual(row["review"]["passing_tasks_broken_by_review"], len(reviews[row["arm"]]["broken_by_review"]))
        agents = self.text("AGENTS.md")
        for required in ("evidence.json", "--json", "What to tell your operator", "verify.py"):
            self.assertIn(required, agents)

    def test_front_pages_quote_the_published_reports(self) -> None:
        import json
        features = {row["arm"]: row for row in json.loads(self.text(
            "case-studies/feature-benchmark-2026-11-10/report.json"))["arms"].values()}
        pairs = {row["arm"]: row for row in json.loads(self.text(
            "case-studies/paired-features-2026-11-10/report.json"))["arms"].values()}
        facts = [f"${float(features[arm]['usd_per_task']):.3f}" for arm in ("astra-solo", "frontier-solo", "klp-3")]
        facts += [f"${float(pairs[arm]['usd_per_pair']):.3f}" for arm in ("solo", "semio")]
        facts += [str(pairs["semio"]["model_calls"]), str(pairs["chat"]["model_calls"])]
        self.assertEqual((features["klp-3"]["solved"], features["astra-solo"]["solved"], features["frontier-solo"]["solved"]),
                         (59, 56, 56))
        self.assertEqual((pairs["semio"]["solved"], pairs["chat"]["solved"], pairs["solo"]["solved"]), (28, 28, 22))
        for page in ("README.md", "BENCHMARKS.md", "AGENTS.md", "EVIDENCE.md"):
            text = self.text(page)
            for fact in facts[:5] if page == "README.md" else facts:
                self.assertIn(fact, text, f"{page} lacks {fact}")

    def test_charts_are_drawn_from_the_published_reports(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location("make_charts", ROOT / "assets" / "make_charts.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        readme = self.text("README.md")
        for name, (title, subtitle, rows) in module.charts().items():
            for mode, theme in module.THEMES.items():
                self.assertEqual(self.text(f"assets/{name}-{mode}.svg"), module.chart(title, subtitle, rows, theme),
                                 f"{name}-{mode}.svg is stale; run python3 assets/make_charts.py")
                self.assertIn(f"assets/{name}-{mode}.svg", readme)

    def test_one_command_covers_every_case_study_checker(self) -> None:
        import sys
        sys.path.insert(0, str(ROOT))
        from bench import features, verify
        listed = {script for _, script in verify.CHECKERS}
        present = {str(path.relative_to(ROOT)) for path in ROOT.glob("case-studies/*/verify.py")}
        self.assertEqual(listed, present)
        for arms in features.PRESETS.values():
            for arm in arms.split(","):
                self.assertIn(arm, features.ARMS)
        for page in ("README.md", "BENCHMARKS.md", "AGENTS.md", "VERIFY.md", "llms.txt"):
            self.assertIn("bench.verify", self.text(page))
        self.assertIn("python3 -m bench.verify", self.text(".github/workflows/ci.yml"))

    def test_readme_leads_with_standard_and_a_runnable_demo(self) -> None:
        readme = self.text("README.md")
        self.assertLess(readme.index("## Start Here"), readme.index("## What You Gain"))
        self.assertLess(readme.index("## Try the Demo"), readme.index("## What You Gain"))
        start = readme.split("## Start Here", 1)[1].split("## Try the Demo", 1)[0]
        self.assertIn("Standard", start)
        self.assertIn("examples/standard-task.md", start)
        self.assertIn("examples/solo-operator.md", start)
        self.assertIn("VERIFY.md", readme)
        self.assertIn("runtime controls", readme)

    def test_solo_guide_keeps_actual_identity_separation(self) -> None:
        guide = " ".join(self.text("examples/solo-operator.md").split())
        for required in (
            "not a requirement for separate human employees",
            "Renaming the same session", "Mission Custodian", "Coordinator",
            "Capability Auditor", "cannot claim Critical conformance",
            "same-family", "standing delegation",
        ):
            self.assertIn(required, guide)

    def test_missing_proof_recovery_preserves_stops_authority_and_budget(self) -> None:
        protocol = " ".join(self.text("PROTOCOL.md").split())
        recovery = protocol.split("### Recovering Missing Capability Proof", 1)[1].split(
            "## Required Records", 1
        )[0]
        for required in (
            "capability_unproven", "smallest missing action", "remaining budget",
            "Do not poll", "Mission Amendment Request",
            "pre-work baseline", "exact artifact", "not `completed`",
        ):
            self.assertIn(required, recovery)
        self.assertIn(
            "recovering-missing-capability-proof",
            self.text("AI_AGENT_INTEGRATION.md"),
        )

    def test_public_verification_separates_execution_from_receipt_arithmetic(self) -> None:
        guide = " ".join(self.text("VERIFY.md").split())
        for required in (
            "scripted worker", "loopback fake critic", "Python 3.12",
            "No API keys", "not a replay of the private coding task",
            "capability-after-integration-1.json", "capability-after-integration-2.json",
            "case-studies/krystalview-2026-10-20/verify.py",
            "case-studies/semio-coordination-2026-10-20/verify.py",
        ):
            self.assertIn(required, guide)
        workflow = self.text(".github/workflows/ci.yml")
        for command in (
            "python3 tests/test_v03_documentation.py -v",
            "python3 -m unittest discover -s examples/capability-regression/tests -v",
            "python3 case-studies/krystalview-2026-10-20/verify.py",
            "python3 case-studies/semio-coordination-2026-10-20/verify.py",
        ):
            self.assertIn(command, workflow)


if __name__ == "__main__":
    unittest.main()
