# Standard Task Record

Template only: replace placeholders before dispatch. Keep this in a versioned
issue or Markdown file, not solely in chat. One record can contain all sections.
See [profile selection](../EXECUTION_PROFILES.md) before choosing Standard.

## Before Work

- protocol: klp-standard/v0.1
- task_id / record_revision / parent_revision: <stable ID and version history>
- authority_ref: <operator request or standing policy covering this task>
- product_promise_ref: <exact version of approved product purpose; Mission Contract if present>
- profile_reason: <affected behavior and evidence that no Critical trigger matches>
- outcome / acceptance: <observable result and required non-regressions>
- base_revision: <exact snapshot including any relevant uncommitted files>
- owner / coordinator / reviewer_identity: <distinct worker and critic; family disclosed>
- allowed_paths: <initial files or narrow directory and permitted edit types>
- protected_paths / forbidden_actions: <explicit exclusions, including live actions>
- adjacent_edit_allowance: none
  <Or pre-authorized narrow directory/candidate set, edit type and max extra files>
- checks / expected_results: <commands, assertions and evidence locations>
- test_environment: <allowlisted environment, synthetic data, external network denied>
- time_limit / cost_limit / repair_limit: <finite shared caps; include review and close-out>
- reviewer_timeout / extra_reads / retry_policy: <finite, authorized and within caps>
- escalation: <Critical trigger, out-of-scope edit, exhausted limit, missing proof>

## Work and Review

- result_revision / integration_revision: <exact candidate and integrated contents>
- factual_changes / check_results / evidence_refs: <what ran, actual results, artifact>
- adjacent_edits_used: <file, reason, coordinator decision, checks, remaining allowance>
- critic: <identity, family, reviewed artifact, verdict and evidence reference>
- finding_dispositions:
  <ID; confirmed/refuted/unresolved; blocking yes/no; commitment; direct evidence; decision>
- repairs / rechecks: <bounded changes and refreshed evidence, or none>

## Completion

- state: <completed / blocked / plateau / budget_exhausted / material_change / safety_stop / ready_for_authority_decision>
- supported_outcome / integration_result: <evidence-backed result, not worker self-acceptance>
- measured_effort: <elapsed time, reviews, repairs, available usage; unknown costs explicit>
- limitations / unresolved_findings: <honest remaining gaps; required proof cannot be waived>
- human_decisions_required: <push/deploy/live actions, or none>

Standard completion requires passing executed checks, review applicable to the
exact final contents, disposition of every finding and no open blocking finding.
If a Critical trigger is discovered, stop affected work and retain this record
while establishing Core authority and baseline. Do not relabel it as a passed
Core run, or downgrade an existing Core run to use this template.
