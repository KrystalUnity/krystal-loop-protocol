# AI Agent Integration Guide

This guide tells an AI agent, orchestrator, or agent framework how to operate
under KLP without depending on a particular model or tool stack.

## Choose the Execution Profile First

Read [Execution Profiles](EXECUTION_PROFILES.md) before dispatch. For ordinary
bounded work with no Critical trigger, use `klp-standard/v0.1` and the
[compact task record](examples/standard-task.md). Its profile guide is the
complete Standard checklist; do not import every Core record below into it.

In the existing Standard critic pass, include the exact project-policy/mission
references and assess `profile_assessment`: `eligible`, `critical_trigger` or
`insufficient_evidence`, with evidence from the exact final candidate. Missing or
unresolved eligibility blocks Standard acceptance; a true Critical trigger uses
the escalation path. The coordinator's label alone is not confirmation.
Prefer behavior-based triggers when authoring missions, but never narrow an
existing file-wide trigger without the required operator-approved amendment.

For routine shipping, use the [release gate](EXECUTION_PROFILES.md#routine-release-gate)
instead of automatically converting every Standard task to Core. Assess the full
bundle, run applicable artifact-bound probes, retain rollback and operator
authority, and verify activation. Critical changes retain the full Core gate.

The required capabilities, bootstrap, minimum record shape, envelope and
capability gate below describe **Critical / `klp-core/v0.3`** unless a section
explicitly says it applies to both profiles. Existing runnable examples keep
their stated versions; Standard is not automatically supported by their validators.
Shared authority, data handling and evidence-based finding decisions apply to both.

One operator can use separate agent identities; see the
[solo-operator example](examples/solo-operator.md). Infrastructure Profile A
means local files, not relaxed review. Standard/Critical selects the required
assurance; infrastructure profiles select how records and messages are stored.

## Required Capabilities

An implementation is KLP-compatible when it can:

- preserve an authorized task contract with identity and revision lineage;
- recover the exact Mission Contract from authoritative durable storage rather
  than conversational memory;
- bind every v0.3 task to `mission_id`, `mission_revision`, and `mission_hash`;
- identify trigger-matched `affected_capabilities[]` and run required
  integrated-artifact capability probes;
- assign bounded work units with explicit owners and paths;
- identify the exact base and result artifact revisions;
- run or record deterministic checks;
- store direct evidence and reference it from findings;
- disposition every critic finding with evidence;
- separate worker and critic identities for the same artifact;
- represent stops, repairs, dependencies, and limitations;
- enforce declared repair, time, cost, and other measurable limits;
- re-check the integrated artifact;
- leave live actions behind a human-controlled decision point.

Persistent memory, vector search, MCP, Redis, a relational database, and a
specific model provider are optional.

## Agent Bootstrap Instructions

Every role beginning a v0.3 KLP task reads the exact Mission Contract and
current state from authoritative durable storage, then follows this order:

1. Confirm the Mission Contract `mission_id`, `mission_revision`, and
   `mission_hash`, including critical capabilities, triggers, accepted
   baselines, controls, and revision authority.
2. Read the Task Contract and confirm that its mission identity exactly matches
   the canonical Mission Contract.
3. Confirm the contract identity, assigned work unit, exact base revision,
   delegation, allowed paths, protected paths, dependencies, forbidden actions,
   checks, evidence, required capability probes, and measured limits.
4. Verify every trigger match is declared in `affected_capabilities[]`.
5. Stop before editing if mission identity or the assignment is missing,
   contradictory, stale, wider than the approved task, or has an undeclared
   trigger match.
6. Work only inside the assignment boundary.
7. Run the declared checks and capture exact results.
8. Return a factual handover tied to the result revision.
9. Do not declare your own artifact accepted or claim preservation.

Before dispatch, the coordinator follows
[Choosing And Reassessing The Approach](PROTOCOL.md#choosing-and-reassessing-the-approach).
Define observable completion and prefer existing operational paths and checks.
Record why new tooling or additional verification is necessary. Preserve one
total effort budget across planning, child tasks, reviewer retries, waiting,
repairs, and close-out; replacement agents recover the remaining budget.

After two unsuccessful cycles toward the same unmet outcome, when new tooling
becomes the main blocker, or when the operator redirects the task, reassess the
approach before continuing. Use the existing task record for the evidence,
decision, next sufficient action, and remaining budget. Workers report the need
for reassessment to the coordinator; they cannot revise their own assignment.
Simplification within delegation is allowed, but binding commitments, required
checks, capability preservation, and authority boundaries remain intact.
Coordinate overlapping skill and review requirements in one review plan.

Critics must start from fresh read-only context containing the task contract,
exact artifact revision, check results, direct evidence, and unresolved prior
findings. For both profiles, include whole touched functions (or coherent
sections for large functions), necessary callers, interfaces and tests alongside
the diff. Use bounded additional reads at the same revision for missing context;
do not dump the entire repository or treat a bare diff as complete evidence.
Set a finite provider-specific timeout within the remaining parent budget,
not a blanket 800-second default. A timeout is not a pass; no automatic retry
or model fallback is authorized by this guidance.

A critic must not edit the artifact it reviews. A task critic may
assess declared impact but cannot satisfy the mechanical capability gate or
override a Capability Auditor result.

The Mission Custodian checks mission alignment at approval, repair, integration,
and final review. At `capability_baseline`, pre-work required probes run against
the accepted baseline artifact identified by `accepted_baseline_ref`. At
`capability_check`, post-integration required probes run against the exact
integrated artifact revision. The Capability Auditor publishes observations
without editing either artifact.

## Runnable Worker and Critic Path

The repository includes a concrete endpoint-backed example while keeping the
control layer provider-neutral:

1. Copy and review
   [`assignment.example.md`](examples/deepseek-codex-worker/assignment.example.md).
2. Export `DEEPSEEK_API_KEY` in the current shell and launch the bounded worker
   with
   [`run.sh`](examples/deepseek-codex-worker/run.sh).
3. Independently run the declared checks and record the exact result revision.
4. Build and redact a sealed packet from
   [`review-packet.example.json`](examples/openai-compatible-critic/review-packet.example.json).
5. Configure a different provider family and run
   [`critic.py`](examples/openai-compatible-critic/critic.py). Same-family
   review requires the explicit `--allow-same-family` escape and is not
   independent.
6. Validate the critic artifacts and present the evidence to the human
   decision-maker.

The worker configuration points Codex at DeepSeek's OpenAI-compatible endpoint,
but the endpoint is only the inference engine. The assignment, workspace
sandbox, deterministic checks, sealed evidence, critic separation, and human
authority remain outside the model. A workspace sandbox does not enforce an
assignment's per-file allow-list; the controller must inspect the changed-file
set and exact diff.

The critic harness accepts any compatible `/chat/completions` endpoint through
environment variables. It makes one request and performs no retry, repair,
merge, push, or deployment. Different-family review is the default, but family
labels are controller declarations rather than identity attestation.

Do not feed credentials, private logs, or unreviewed context to the critic. The
controller owns packet construction and redaction. Packet contents remain
untrusted evidence, and a valid `verdict.json` is evidence, not permission.

## Minimum Record Shape

Record formats may vary, but an agent must be able to recover these fields:

```text
protocol
mission_id
mission_revision
mission_hash
parent_mission_hash
task_id
contract_id
contract_revision
contract_hash
parent_contract_hash
unit_id
state
objective
commitments[]
affected_capabilities[]
capability_commitments[]
expected_capability_delta
required_capability_probes[]
baseline_evidence_refs[]
base_revision
result_revision
owner
allowed_paths[]
protected_paths[]
forbidden_actions[]
dependencies[]
checks[]
evidence_refs[]
findings[]
finding_dispositions[]
capability_risks_observed[]
capability_report
coordinator_may[]
must_escalate[]
round_limit
time_limit
cost_limit
measured_budget
limitations[]
human_decisions_required[]
```

Omitting a field is acceptable only when the field is inapplicable and the
record says why. Empty evidence must not be presented as successful evidence.

For a v0.3 Task Contract, `expected_capability_delta` is `preserve` or
`improve`. A final `capability_report` compares before and after probes for each
affected capability and records `preserved`, `improved`, `degraded`, or
`unproven`; only the first two permit completion.

Each capability probe records `capability_id`, `mission_hash`,
`artifact_revision`, `baseline_revision`, `positive_control`,
`negative_control`, `expected_observations`, `actual_observations`,
`decision_provenance`, `limits`, `result` (`passed`, `failed`, or
`inconclusive`), and `evidence_refs[]`.

An absent, stale, inconclusive, failed, or otherwise unusable pre-work baseline
is classified as `capability_unproven`; `capability_regression` is reserved for
post-integration evidence that falls below the frozen accepted baseline.

A Mission Amendment Request contains `protocol_version`, `request_id`,
`mission_id`, `current_mission_hash`, `requested_change`,
`technical_explanation`, and `operator_impact_statement`. Its technical
explanation covers fields changed, evidence, behavioral, architectural,
testing, safety, and compatibility impact, alternatives, rollback, and
duration. Its plain-English Operator Impact Statement covers today, after, user
loss, expected benefit, and the consequence of declining. Only the human
operator may authorize the resulting Mission Contract revision.

## Generic Coordination Envelope

KLP does not require a message bus. When agents communicate through one, the
transport should preserve an envelope similar to:

```json
{
  "protocol": "klp-core/v0.3",
  "message_id": "msg-unique-id",
  "mission_id": "mission-example",
  "mission_revision": 1,
  "mission_hash": "sha256:mission-digest",
  "task_id": "task-example",
  "contract_id": "task-example",
  "contract_revision": 1,
  "unit_id": "unit-parser",
  "from": "worker-parser",
  "to": "coordinator",
  "kind": "status",
  "correlation_id": "question-or-flow-id",
  "in_reply_to": null,
  "artifact_revision": "revision-or-digest",
  "affected_capabilities": [],
  "capability_report_ref": null,
  "evidence_refs": [],
  "summary": "Bounded factual status without raw private logs.",
  "timestamp": "2026-01-01T00:00:00Z"
}
```

Recommended `kind` values are `status`, `question`, `answer`, `handover`,
`finding`, and `stop`. Messages are transport, not authority. Long findings and
evidence should live in durable storage and be referenced rather than copied
into every message.

## Worker Handover

A useful handover answers:

1. What exact revision was produced?
2. What changed, factually?
3. Which declared checks ran, with what results?
4. Where is the direct evidence?
5. Which `capability_risks_observed[]` arose from the work?
6. What remains uncertain or blocked?

A worker reports facts and observed risks but cannot claim preservation,
improvement, or completion. Avoid persuasive completion language, hidden
reasoning, raw secrets, and unbounded logs.

## Critic Output

Each finding should contain:

```text
finding_id
severity
status
affected_commitments[]
observed
expected
evidence_refs[]
repair_acceptance
recurrence_key
blocking
```

Suggested verdicts are `PASS`, `PASS_WITH_NONBLOCKING_FINDINGS`, `NEEDS_FIXES`,
`BLOCKED`, and `ESCALATE`. A pass verdict cannot coexist with an open blocking
finding.

The coordinator must adjudicate each finding against direct evidence from the
exact reviewed artifact. Record `confirmed`, `refuted`, or `unresolved` plus
the evidence references and rationale. A critic verdict is not self-executing,
but an unresolved blocking finding still prevents acceptance.
Task checks and critic verdicts cannot override `capability_regression` or
`capability_unproven`.

Use `commitment` (or `affected_commitments[]`) to identify the actual acceptance
requirement, and `evidence_refs[]` for its supporting evidence or missing required
proof. In `observed` or the disposition rationale, distinguish an existing
defect, a requested-change regression, an agent-created tooling defect, an
optional improvement, or unknown origin. Explain the smallest sufficient
resolution in `repair_acceptance`; do not invent requirements or demand a new
harness when existing evidence suffices. A tooling defect also calls for
reassessing whether the tooling is necessary. Report unrelated issues separately
without turning them into blockers unless they prevent safe authorized work.
The existing verdict schema is unchanged; these explanations use its current
fields.

For both profiles, use `blocking` separately from the truth disposition. A
reviewer's requested condition is not a new acceptance condition unless it
implements an actual commitment or missing required proof. For example, refute
a demanded changed sim hash with source/trace evidence if the bot never reaches
the changed behavior, then verify that behavior with a relevant probe. Refuting
the hash demand does not prove the feature. Record the decision once; a refuted
or advisory note does not require another critic round merely to obtain silence.

## Stop Behavior

An agent must stop and report rather than improvise when:

- the Mission Contract identity is missing, stale, unknown, or does not match
  the Task Contract: `mission_mismatch`;
- a capability trigger matches changed surfaces but is undeclared:
  `mission_mismatch`;
- the requested change exceeds allowed paths or actions;
- a required dependency or credential is unavailable;
- the base artifact changed beneath the assignment;
- a deterministic check fails and no bounded repair remains;
- a required baseline, capability probe, or integrated-artifact evidence is
  missing, unavailable, invalid, or inconclusive: `capability_unproven`;
- a post-integration capability probe fails by falling below the frozen
  accepted baseline: `capability_regression` and no acceptance claim;
- a requested repair would weaken a capability, its controls, baseline,
  triggers, severity, or provenance requirement:
  `mission_amendment_requested`;
- the same blocking finding recurs to the declared plateau limit;
- cost, time, or round budget is exhausted;
- continuing would require a live or destructive action not explicitly
  approved by a person.

Only a repair inside the frozen Task Contract and Mission Contract may proceed
after `capability_regression`. A live or consequential probe is not run without
explicit operator authority; its absence is `capability_unproven`.
For v0.3 critical-capability evidence failures, `capability_unproven` takes
precedence over the generic `blocked` state.

For a resumable stop, follow
[Recovering Missing Capability Proof](PROTOCOL.md#recovering-missing-capability-proof):
preserve exact identities and evidence, name the missing proof and smallest
next action, identify its owner/authority and retain the remaining budget.
Return this handover instead of polling for approval or starting repeated
reviews. Do not turn completed implementation into a completed Critical run
while proof is missing. Resume at the blocked gate only when its prerequisites
are satisfied; no silent proof substitution, late baseline or budget reset.

## Integration Checklist

Before completing a combined result or presenting a consequential decision:

- verify every accepted unit revision is the one integrated;
- inspect shared contracts and overlapping behavior;
- run relevant unit and integration checks again;
- have a fresh critic review the combined artifact when risk warrants it;
- verify Mission Contract binding and every declared capability trigger;
- run each required capability probe on the integrated artifact;
- record every final disposition and evidence in the `capability_report`;
- record unresolved limitations and missing evidence;
- list every consequential action that still requires a human decision. When
  this list is empty and all capability dispositions are `preserved` or
  `improved`, the bounded v0.3 run may complete without another approval click.

Existing v0.2 records and lifecycle proof remain valid for v0.2, but cannot
claim v0.3 conformance without Mission Contract binding and the capability gate.
