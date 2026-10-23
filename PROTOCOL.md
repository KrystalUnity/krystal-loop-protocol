# KLP Core Protocol

Status: provisional public profile

Version: 0.3.3 draft

Record format: `klp-core/v0.3` (unchanged). This is the **Critical** execution
profile. This draft clarifies Standard profile review, routine release gates
and project economy policy without changing the Core record schema or capability gate.

Start with [Execution Profiles](EXECUTION_PROFILES.md). Ordinary bounded work
may use the separate `klp-standard/v0.1` compact record when its eligibility
checks pass. Standard does not claim Core v0.3 conformance. The lifecycle,
required records and hard rules below govern Critical/Core runs; neither
profile authorizes live action or a silent mission change.

Standard's critic also checks its eligibility; ordinary deployment permission is
handled separately by the [routine release gate](EXECUTION_PROFILES.md#routine-release-gate).
Critical release bundles retain all applicable Core proofs and authorization.

## Purpose

KLP Core defines the minimum operating discipline for bounded, reviewable
multi-agent project work. It is provider-neutral and transport-neutral.

The protocol separates four different claims:

1. a bounded task was authorized by an explicit contract or standing delegation;
2. a worker produced an artifact;
3. checks and an independent critic evaluated that artifact;
4. a person separately authorized any consequential action that remained.

No earlier claim implies a later one. KLP v0.3 additionally requires a
product-truth capability gate so that task-local acceptance cannot conceal a
critical capability regression.

## Authority Hierarchy

The authority order is:

```text
Human operator
  -> Mission Contract
    -> Task Contract
      -> Work-unit assignments
        -> implementation, checks, criticism, and repair
      -> integrated artifact
    -> capability gate
  -> consequential action decision
```

A lower layer cannot weaken or reinterpret a higher layer. Task Contracts and
plans are disposable after their run. A Mission Contract persists until the
human operator authorizes a versioned amendment. KLP itself never authorizes a
consequential action.

## Mission Contract

Every `klp-core/v0.3` run must bind to one canonical Mission Contract stored in
authoritative durable storage. Agents recover it from that record, not from
conversational memory. JSON, YAML, Markdown with structured front matter, or
an equivalent immutable record is valid only when its canonicalization and
digest method are declared.

The executable record shape separates immutable identity from the mission body:

```text
identity.protocol_version
identity.mission_id
identity.mission_revision
identity.mission_hash
identity.parent_mission_hash
identity.authority_ref
identity.created_at
mission.product_outcome
mission.critical_capabilities[]
mission.forbidden_regressions[]
mission.operator_revision_authority
mission.revision_reason
```

`parent_mission_hash` is null only for revision 1; every later revision records
its parent. At least one critical capability is required. Each critical
capability contains:

```text
capability_id
required_behavior
severity: critical
trigger_rules[]
positive_control[]
negative_control[]
proof_method
accepted_baseline_ref
decision_provenance_requirement
```

The accepted baseline is the most recent operator-accepted product-truth
evidence. Test counts, coverage, critic confidence, and worker assertions do
not replace it. Trigger rules may cover paths, symbols, dependency edges, APIs,
schemas, configuration, prompts, models, data contracts, or runtime behavior.

When authoring triggers, prefer protected behavior and claims over blanket file
matches: for example, changes to the source or meaning of displayed persistent
balances, rather than every panel in a UI file. Paths/symbols help discover impact;
they do not replace behavioral analysis or exclude effects from other files.
Existing whole-file triggers remain binding. Narrowing trigger scope is a Mission
Amendment Request with technical and plain-English explanation, not an agent's
classification shortcut. See [trigger guidance](EXECUTION_PROFILES.md#author-behavior-based-mission-triggers).

## Roles

| Role | Responsibility |
| --- | --- |
| Human operator | Defines authority boundaries and makes consequential lifecycle decisions. |
| Mission Custodian | Re-reads and protects the frozen Mission Contract, verifies capability impact at approval, repair, integration, and final review, and does not implement or troubleshoot worker code for the same critical run. |
| Capability Auditor | Mechanically runs approved integrated-artifact product-truth probes and publishes immutable observations without editing the artifact. |
| Coordinator | Preserves the authorized outcome and delegation, chooses and reassesses the approach, assigns work, adjudicates findings, tracks total effort, and integrates evidence. |
| Worker | Produces one bounded outcome and a factual handover. |
| Verifier | Runs deterministic checks and captures direct evidence. |
| Critic | Independently judges one exact artifact revision without modifying it. |
| Integrator | Combines accepted units and owns verification of the combined result. |

One person or agent may hold several roles at different times, but a worker
must not act as the independent critic of the same artifact. For work affecting
a critical capability, the Mission Custodian and Coordinator must be different
identities. The Capability Auditor cannot be the worker whose artifact it
checks and cannot alter observations at a coordinator's request. Existing
worker and critic independence remains mandatory for the same reviewed artifact.

## Core Lifecycle

```text
draft
  -> mission_binding_check
  -> approved
  -> capability_baseline
  -> assigned
  -> building
  -> mechanical_check
  -> critic_review
  -> accepted_unit
  -> integrating
  -> capability_check
  -> final_review
  -> completed
```

Repair returns `critic_review -> needs_fixes -> building`.
After a failed integrated capability check, bounded repair follows:

```text
capability_check
  -> capability_regression
  -> building
  -> mechanical_check
  -> critic_review
  -> integrating
  -> capability_check
```

Use `ready_for_authority_decision` instead of `completed` only when a material
change or consequential action remains. Normal bounded repair rounds do not
require repeated human approval. All existing round, time, and cost limits
apply to capability-aware repair.

First-class stop states are:

- `blocked`: a dependency, capability, or required proof is missing;
- `material_change`: the approved objective or boundary would need to change;
- `plateau`: blocking findings are recurring without measurable progress;
- `budget_exhausted`: a declared time, cost, or round limit was reached;
- `safety_stop`: a secret, destructive action, authority boundary, or other
  hard guard was crossed;
- `accepted_with_limitations`: the artifact is usable only with recorded gaps.
- `mission_mismatch`: a task is unbound, bound to the wrong Mission Contract
  identity, or omits a triggered capability;
- `capability_regression`: an integrated artifact measurably degrades a
  critical capability;
- `capability_unproven`: required capability evidence is missing, unavailable,
  invalid, or inconclusive;
- `mission_amendment_requested`: satisfying the task would require changing a
  mission commitment.

`mission_mismatch`, `capability_unproven`, and
`mission_amendment_requested` stop affected work. `capability_regression`
stops acceptance and can return only to bounded repair within the frozen Task
Contract and Mission Contract. If no such repair remains, the terminal receipt
uses the applicable stop, such as `budget_exhausted`, and records the capability
as `degraded`. A critical capability with disposition `degraded` or `unproven`
can never be accepted as `accepted_with_limitations` or `completed`.

For v0.3 critical-capability evidence failures, `capability_unproven` takes
precedence over the generic `blocked` state.

## Required Records

KLP implementations may combine records, but must preserve these facts:

| Record | Required content |
| --- | --- |
| Mission Contract | Identity, product outcome, critical capabilities, controls, triggers, accepted baselines, decision provenance requirements, forbidden regressions, amendment authority, and revision reason. |
| Mission Binding Report | `mission_identity`, `contract_identity`, `changed_surfaces`, `triggered_capabilities`, `declared_capabilities`, actor identities, and verifier result. |
| Capability Baseline | `capability_id`, `mission_hash`, `artifact_revision`, `baseline_revision`, controls, expected and actual observations, decision provenance, limits, `result`, and `evidence_refs[]`. |
| Capability Report | Before/after comparison, disposition for every affected capability, probe results, and evidence. Dispositions are `preserved`, `improved`, `degraded`, or `unproven`. |
| Mission Amendment Request | Requested delta, technical explanation, plain-English Operator Impact Statement, alternatives, evidence, rollback implications, duration, and requested operator authority. |
| Task contract | Contract ID, revision, parent identity, objective, authorized scope, delegation, forbidden actions, checks, evidence, measured limits, and stops. |
| Work-unit assignment | Outcome, owner, exact base revision, allowed paths, dependencies, and limits. |
| Worker handover | Exact result revision, factual changes, check results, evidence references, `capability_risks_observed[]`, and open concerns. |
| Evidence report | Commands or observations, results, timestamps, artifact identity, and data-handling status. |
| Critic verdict | Exact reviewed revision, commitment assessments, findings, evidence references, and next action. |
| Finding disposition | Finding ID, `confirmed`, `refuted`, or `unresolved` status, artifact revision, rationale, and direct evidence references. |
| State event | Append-only sequence, previous state, new state, reason, actor, timestamp, contract revision, mission revision, mission hash, artifact revision, and supporting evidence. |
| Invalidation receipt | Prior contract or evidence identity, replacement identity, causal evidence, authority basis, and reason. |
| Final receipt | Supported claims, limitations, integration result, unresolved findings, measured limits, human decisions still required, Mission Contract identity, and Capability Report. |

## Hard Rules

1. An identified, authorized Task Contract must exist before implementation begins.
2. A v0.3 task cannot be approved without exact Mission Contract binding:
   `mission_id`, `mission_revision`, and `mission_hash` must match the canonical
   Mission Contract.
3. Trigger matches must be declared in `affected_capabilities[]` and verified
   against changed surfaces. An undeclared triggered capability is
   `mission_mismatch`.
4. Every worker must have an explicit outcome and file/action boundary.
5. A worker handover reports facts and cannot issue its own acceptance verdict.
6. Deterministic checks run before model-based criticism whenever such checks
   are available.
7. A critic must be independent, read-only, and bound to the exact artifact
   revision it judges.
8. Every critic finding must be confirmed, refuted, or left unresolved using
   direct evidence. An unresolved blocking finding prevents acceptance.
9. Paths outside the authorized boundary, new dependencies, side effects,
   architecture, or acceptance criteria are material changes and stop execution
   for human review. Exercising an explicit pre-authorized adjacent-edit allowance
   is not a boundary change; see Contract Identity And Delegation.
10. Repair loops have declared round, time, and cost limits.
11. Integration is a new artifact and requires its own relevant checks.
12. A critical capability requires an accepted baseline and integrated-artifact
    evidence. A capability probe must include declared controls and, when
    required, decision provenance.
13. `degraded` or `unproven` blocks completion. Task checks and critic verdicts
    cannot override a failed, missing, or inconclusive capability result.
14. A `capability_restriction_candidate` requires direct preservation evidence
    before the integrated artifact can be accepted. This includes narrowing an
    API or tool schema, removing an action or input, replacing adaptive behavior
    with a fixed sequence, moving product judgment into a controller, or
    weakening a control, threshold, trigger, or baseline.
15. Mission amendments require both a technical explanation and a plain-English
    Operator Impact Statement. Changing a capability proof, baseline, trigger
    scope, severity, positive control, negative control, or provenance
    requirement is a mission amendment, not a test correction.
16. Only the human operator may authorize a Mission Contract revision. A
    coordinator, worker, critic, verifier, Mission Custodian, or Capability
    Auditor cannot do so.
17. No KLP record, agent, critic, test, or message can authorize a live action.
18. Contract revisions and invalidations preserve the prior identity, causal
    evidence, and authority basis instead of silently replacing history.
19. Additional investigation, tooling, checks, repairs, and reviews must address
    a specific unmet requirement or credible risk in the affected scope. An
    agent's chosen implementation is not itself a product requirement.
20. The coordinator reassesses unsuccessful approaches and enforces one total
    task budget across planning, delegation, review, repair, and completion.

## Contract Identity And Delegation

Every contract needs a stable ID and revision identity. A Git revision, content
digest, or immutable record ID is sufficient when its canonicalization method
is declared. A revised contract records its parent identity and reason.

In addition to v0.2 contract facts, every v0.3 Task Contract carries:

```text
mission_id
mission_revision
mission_hash
affected_capabilities[]
expected_capability_delta: preserve | improve
required_capability_probes[]
baseline_evidence_refs[]
```

A task may declare no affected capability only when changed paths, interfaces,
configuration, and behavior match no `trigger_rules[]`; the Mission Custodian
must verify that declaration. A task cannot authorize degradation. A proposed
degradation enters `mission_amendment_requested`.

A contract may give the coordinator standing authority for bounded operations
such as running declared checks, invalidating evidence made stale by a new
artifact revision, adjudicating findings with direct evidence, and applying
repairs inside frozen scope and limits. That delegation avoids a human approval
click on every normal repair round.

Delegation cannot silently change the objective, acceptance criteria, authorized
path boundary, side effects, resource ceilings, Mission Contract, or capability gate.
Correcting a test implementation so it matches frozen criteria may be
delegated; changing the criteria themselves is a material change.

An upfront adjacent-edit allowance may name a narrow directory or candidate set,
edit types, maximum extra-file count and exclusions. Before adding a file under
that allowance, record the coordinator decision, rationale, required checks and
remaining allowance; rerun mission trigger matching. Without an explicit allowance,
an exact file list remains exact. This is use of delegated scope, not permission
to expand it. See [bounded adjacent edits](EXECUTION_PROFILES.md#small-related-edits-without-scope-drift).

The contract should distinguish binding implementation commitments from
agent-selected implementation details. Delegation may permit simplifying those
details, including abandoning newly introduced tooling, inside the same outcome,
paths, architecture boundary, side effects, required checks, and limits. Record
the decision and invalidate affected evidence. Removing a binding commitment
still requires an authorized contract revision; simplification never permits
discarding unrelated work or weakening a Mission Contract.

## Product-Truth Capability Gate

At `capability_baseline`, pre-work required probes run against the accepted
baseline artifact identified by `accepted_baseline_ref`. At `capability_check`,
post-integration required probes run against the exact integrated artifact
revision. A live or consequential probe needs separate operator authority;
when it cannot run, record `capability_unproven`.

An absent, stale, inconclusive, failed, or otherwise unusable pre-work baseline
is classified as `capability_unproven`; `capability_regression` is reserved for
post-integration evidence that falls below the frozen accepted baseline.

Each probe record contains `capability_id`, `mission_hash`,
`artifact_revision`, `baseline_revision`, `positive_control`,
`negative_control`, `expected_observations`, `actual_observations`,
`decision_provenance`, `limits`, `result` (`passed`, `failed`, or
`inconclusive`), and `evidence_refs[]`. The final disposition is `preserved`,
`improved`, `degraded`, or `unproven`; only the first two pass the capability
gate. Scheduled monitoring supplements, and never replaces, integration checks.

## Mission Amendment Request

A Mission Amendment Request pauses affected work and requires a direct operator
decision. It contains `protocol_version`, `request_id`, `mission_id`,
`current_mission_hash`, `requested_change`, `technical_explanation`, and
`operator_impact_statement`. The technical explanation records
`fields_changed`, `evidence_refs`, behavioral, architectural, testing, safety,
and compatibility impact, alternatives, rollback implications, and duration.

The plain-English Operator Impact Statement states: "Today the product can...",
"After this amendment, it will...", "The user may lose...", "The expected
benefit is...", and "If you decline, the consequence is...". An amendment
missing either explanation is invalid. An authorized revision records its
`parent_mission_hash`, `authority_ref`, and reason; rejection leaves the prior
Mission Contract unchanged.

## Choosing And Reassessing The Approach

Before dispatch, define observable completion, required capability preservation,
and the existing checks or operational path that can establish them. For an
existing capability, first assess whether the authorized outcome can be reached
through its current configuration and workflow.

Before adding investigation, a helper, a harness, a check, a repair, or another
review, identify the unmet requirement or credible risk, the supporting evidence
or precise evidence gap, and what decision the next bounded step will resolve.
Use the smallest sufficient method. Extend existing checks before creating a
new harness, and create one only when existing methods cannot adequately verify
something necessary. Direct source analysis or observation can establish a
defect; not every concern needs a new executable reproduction. New checks must
stay within delegation and must not silently add acceptance criteria.

Reassess the approach after two unsuccessful plan, review, or repair cycles
toward the same unmet outcome, even if finding IDs or individual defects change.
A cycle is a completed attempt to resolve that outcome followed by its check or
review; tool calls and ordinary implementation steps are not separate cycles.
Reassess sooner when agent-created tooling becomes the main source of blockers
or the operator redirects the task, asks to simplify, or asks why it is not
finished. A stricter declared stop or budget limit takes precedence.

In the existing task record, briefly record:

- the remaining unmet outcome and where its blockers originated;
- what the attempts actually established, including problems introduced by the
  approach itself;
- whether to continue, simplify, abandon or defer optional tooling, or stop;
- the next sufficient action, its expected evidence, and the remaining budget.

Continue only with an evidence-backed reason or a materially different approach
inside delegation. Otherwise stop affected work as `plateau`, `blocked`, or the
applicable existing stop. A reassessment is not an automatic request for another
human approval, a budget reset, or permission to bypass a required check. An
operator correction must affect the next action or receive a concrete explanation
of the remaining binding constraint; an acknowledgement alone is insufficient.

Set an overall effort envelope at intake and retain it in the Task Contract.
Planning, tool construction, checks, reviewer calls and retries, waiting,
repairs, integration, and documentation all consume it. Child assignments and
replacement agents inherit the remaining envelope; new findings, new plans,
context recovery, and delegated workflows do not reset it. Measure elapsed time
once across the parent task and aggregate resource use across its children.
Report unavailable measurements honestly and use enforceable limits rather than
inventing cost or token totals.

When using KLP alongside skills or another review system, select one coordinated
review plan. Reuse evidence that satisfies the same scope, artifact identity,
independence, and freshness requirements. Preserve mandatory gates, but do not
multiply optional reviews merely because several workflows recommend them.
Every additional review must resolve a named requirement or relevant uncertainty.
Progress reports should state changed evidence, remaining work, or a decision;
do not repeatedly describe an unchanged wait as progress.

## Finding Adjudication

A critic verdict is a claim requiring disposition, not an automatic command.
The coordinator records each finding as:

- `confirmed` when direct evidence supports it;
- `refuted` when stronger direct evidence disproves it;
- `unresolved` when available evidence cannot decide it.

Refutation must cite evidence tied to the reviewed artifact. Coordinator
confidence or a persuasive worker response is not sufficient. Confirmed and
unresolved blocking findings remain open until repaired, bounded by the
declared stop limits, or escalated.

Judge a finding's truth separately from whether it blocks acceptance. A blocker
must identify a violated task commitment, protected capability, or applicable
safety/authority constraint and cite direct evidence or a specific missing
required proof. A preference, optional test, or unrelated defect is not a new
acceptance criterion. Report unrelated findings separately without automatically
repairing them; a credible serious risk may stop affected work without
authorizing that repair.

A demonstrated failure condition within supported operating conditions that
violates a task commitment or protected capability blocks acceptance, even if
production has not encountered it. Cite the triggering conditions and evidence
tied to the reviewed artifact. Calling it a "residual" does not reduce its
significance. Theoretical reachability outside the supported conditions is not
enough; neither is proximity to a limit without evidence of crossing it. A
blocking finding stops affected acceptance, not the scope boundary: repair
outside delegation still requires the applicable scope-change decision.

Record the origin in the existing finding or disposition rationale: pre-existing
defect, regression from the requested change, defect in agent-created tooling,
or optional improvement. Use `unknown` when evidence cannot establish origin.
For tooling defects, reassess whether the tooling is needed before repairing it.
Removing unnecessary tooling may resolve the problem, provided the authorized
outcome and required protections are still met and the resulting artifact is
verified. Neither origin nor severity alone determines blocking status.

### Worked Example: Size Limits

This is a hypothetical example, not a verified production incident. All sizes
refer to the actual serialized bytes measured at the enforcing boundary, using
KiB (1,024 bytes), not in-memory objects or rounded display values.

- A supported result is 77 KiB and its required store rejects values above
  64 KiB. This violates the persistence commitment and blocks acceptance;
  waiting for a production failure adds no necessary evidence.
- A 77 KiB result against a 131 KiB ceiling does not alone demonstrate failure.
  Record the concern and any specific missing required proof; do not invent
  accumulation, duplication, or encoding overhead.
- If the supported workflow must append two such results to one untrimmed
  journal, its payload alone is 154 KiB before envelope overhead. Against that
  same 131 KiB ceiling, verified append/retention behavior and byte measurements
  demonstrate a blocking failure condition.
- A claimed second append that is actually prevented by an enforced supported
  limit does not establish that condition. Cite the enforcement evidence; an
  informal expectation that users will stay below the ceiling is not a bound.

Use the existing finding record for the commitment, supported trigger, actual
measurement or calculation, and disposition. No extra review round or live
production failure is required merely to rename the finding.

## Evidence Order

Use the strongest available evidence:

1. deterministic proof such as tests, type checks, schema validation, replay,
   or measured assertions;
2. direct observation such as a rendered interface, API response, process
   probe, database read, captured log, or performance measurement;
3. independent judgment tied to the first two categories;
4. worker assertion.

Higher categories do not make lower ones useless, but a persuasive summary must
not replace direct proof that was practical to collect.

## Material Change

A material change includes a proposed alteration to the objective, binding
commitments in the accepted plan, scope, architecture boundary, authority,
external side effects, data classification, rollback needs, or resource ceiling.
Simplifying agent-selected implementation details already permitted by the
recorded delegation is not a material change when those boundaries, required
checks, and capability commitments remain unchanged.

When a material change is discovered:

1. stop affected work;
2. record the proposed delta and its impact;
3. preserve the current artifact and evidence;
4. request human review;
5. resume only from a newly authorized task contract revision.

## Completion And Compatibility

A KLP run is complete when declared acceptance criteria are supported by
evidence, every critic finding has a disposition, no blocking finding remains,
the integrated result has been checked, limits are measured, and limitations
are recorded. A v0.3 Final Receipt is incomplete without exact Mission Contract
identity and a Capability Report that gives every affected capability
`preserved` or `improved`. It may reach this state without a per-round human
click.

When these conditions are met, complete the task. Further investigation, checks,
or review require new relevant evidence or an authorized requirement change;
nonblocking findings do not require a zero-finding review cycle. If the requested
runtime behavior is already active while a required gate remains pending, report
both facts explicitly and finish only that remaining gate. A healthy setting
does not establish untested end-to-end behavior.

If merge, release, deployment, spending, credential changes, customer contact,
or production mutation remains, record `ready_for_authority_decision` and list
the exact decisions required. Neither status authorizes those actions by
itself.

Existing v0.2 records remain valid v0.2 records but cannot claim v0.3
conformance. Implementations may support both versions during transition. A
v0.2 task migrates only by creating a Mission Contract, binding a new Task
Contract revision to it, and capturing required baselines; no migration may
silently infer a product mission from old task checks.
