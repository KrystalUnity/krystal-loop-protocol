# KLP v0.3 Capability Preservation Design

Status: Proposed for operator review

Date: 2026-09-03

## Summary

KLP v0.2 can prove that bounded work followed an approved task contract while
missing that the task itself degraded the product's core purpose. Exact-tree
criticism, deterministic checks, and clean integration are insufficient when
all of them inherit incomplete or locally optimized acceptance criteria.

KLP v0.3 adds a versioned Mission Contract above task contracts. Every task is
bound to that mission, declares which critical capabilities it can affect, and
must preserve those capabilities with product-level evidence. A task cannot be
accepted when a critical capability is degraded or unproven, even when its
implementation checks and critic review pass.

## Problem Statement

The protocol currently protects task scope, evidence identity, finding
adjudication, and repair limits. It does not independently preserve the reason
the product exists. This creates a self-validating failure mode:

1. a plan introduces a restrictive implementation;
2. task contracts inherit the restriction;
3. workers implement the tasks correctly;
4. checks prove the restrictive mechanics;
5. critics judge the same local commitments;
6. integration passes while the product loses a core capability.

This is not primarily a context-window failure. Context loss can accelerate it,
but the root defect is that the mission is remembered in conversation instead
of enforced through a separate artifact and product-truth gate.

## Goals

- Make a project's core purpose recoverable without chat history.
- Prevent task plans from silently weakening critical product capabilities.
- Detect product-level regressions before KLP completion.
- Require technical and plain-English explanations for mission amendments.
- Preserve KLP's provider-neutral and transport-neutral design.
- Keep low-risk runs proportionate while making mission binding mandatory.
- Provide an offline proof that green task checks cannot conceal a capability
  regression.

## Non-Goals

- KLP will not define each product's mission or acceptance thresholds.
- KLP will not require a particular CI system, database, scheduler, model, or
  message bus.
- KLP will not authorize deployment, production mutation, spending, customer
  action, or live security testing.
- KLP will not treat one successful model response as universal proof of model
  quality.
- KLP will not make implementation plans permanent governance artifacts.

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

A lower layer cannot weaken or reinterpret a higher layer. Plans and task
contracts are disposable after their run. The Mission Contract persists until
the operator authorizes a versioned amendment.

## Mission Contract

Every v0.3 run must reference one canonical Mission Contract. The canonical
format may be JSON, YAML, Markdown with structured front matter, or an
equivalent immutable record, provided its canonicalization and digest methods
are declared.

Required top-level facts:

```text
protocol_version
mission_id
mission_revision
mission_hash
parent_mission_hash
product_outcome
critical_capabilities[]
forbidden_regressions[]
operator_revision_authority
revision_reason
authority_ref
created_at
```

`parent_mission_hash` is null only for the first revision. At least one critical
capability is required. A small project may use a short contract, but it cannot
omit the product outcome or its primary capability.

### Critical Capability

Each critical capability records:

```text
capability_id
required_behavior
severity
trigger_rules[]
positive_control
negative_control
proof_method
accepted_baseline_ref
decision_provenance_requirement
```

Trigger rules may cover paths, symbols, dependency edges, APIs, schemas,
configuration, prompts, models, data contracts, or runtime behavior. The
positive control proves that the product can perform the behavior. The negative
control distinguishes genuine capability from fixed output, invented success,
or indiscriminate behavior. `decision_provenance_requirement` is used when the
source of a decision matters, such as an AI system being required to select an
action instead of transcribing a pre-authored answer.

The accepted baseline identifies the most recent operator-accepted capability
evidence. Test counts, code coverage, critic confidence, or worker assertions
cannot replace it.

## Task Contract Binding

The v0.3 Task Contract adds:

```text
mission_id
mission_revision
mission_hash
affected_capabilities[]
expected_capability_delta
required_capability_probes[]
baseline_evidence_refs[]
```

`expected_capability_delta` is `preserve` or `improve`. A task cannot authorize
degradation. If degradation is proposed, the task stops and creates a Mission
Amendment Request.

A task may declare no affected capability only when its changed paths,
interfaces, configuration, and behavior do not match any capability trigger.
The verifier checks this declaration. A trigger match that was not declared
causes `mission_mismatch`.

## Lifecycle

The v0.3 lifecycle is:

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

Use `ready_for_authority_decision` instead of `completed` when a separately
controlled consequential action remains.

New first-class stop states are:

- `mission_mismatch`: the task is unbound, bound to the wrong mission revision,
  or failed to declare a triggered capability;
- `capability_regression`: a critical capability is measurably degraded;
- `capability_unproven`: required capability evidence is missing,
  unavailable, invalid, or inconclusive;
- `mission_amendment_requested`: satisfying the task would require changing a
  mission commitment.

For a critical capability, both `capability_regression` and
`capability_unproven` block acceptance. They cannot be converted to
`accepted_with_limitations` merely because local checks passed.

## Roles And Separation

KLP v0.3 adds two roles:

| Role | Responsibility |
| --- | --- |
| Mission Custodian | Re-reads and protects the frozen mission, reviews capability impact, and does not implement or troubleshoot worker code for the same critical run. |
| Capability Auditor | Mechanically executes approved product-truth probes and publishes immutable observations without editing the artifact. |

For work affecting a critical capability, the Mission Custodian and Execution
Coordinator must be different identities. The Capability Auditor cannot be the
worker whose artifact it checks and cannot alter results at a coordinator's
request.

The Mission Custodian validates mission alignment at task approval, every
material-change or repair proposal, integration, and final review. This duty is
performed from the canonical Mission Contract and evidence records rather than
from conversational memory.

Low-risk work may combine other roles when declared. Existing worker and critic
independence remains mandatory for the same reviewed artifact.

The human operator remains the only authority that can amend the mission or
approve consequential actions.

## Product-Truth Probes

A capability probe is a bounded, mechanically evaluated observation of product
behavior. The probe runner may be deterministic even when the system under test
is probabilistic. In that case, the contract declares the sample size,
threshold, allowed variance, cost limit, and inconclusive conditions before the
run.

Each result records:

```text
capability_id
mission_hash
artifact_revision
baseline_revision
positive_control
negative_control
expected_observations
actual_observations
decision_provenance
limits
result
evidence_refs[]
```

`result` is `passed`, `failed`, or `inconclusive`.

The probe must test the integrated artifact rather than only isolated work
units. It must run:

1. before affected work, to verify or capture the accepted baseline;
2. after integration, to compare the resulting capability;
3. after deployment only when separately authorized;
4. on a schedule when an optional runtime profile enables drift monitoring.

Scheduled monitoring supplements integration checks and never replaces them.
A live or consequential probe still needs explicit operator authority. When it
is not authorized or cannot run, KLP records `capability_unproven` rather than
claiming success.

## Capability Disposition

Every affected capability receives one final disposition:

- `preserved`;
- `improved`;
- `degraded`;
- `unproven`.

Only `preserved` and `improved` pass the capability gate. One degraded or
unproven critical capability stops acceptance immediately.

The capability report is part of the Final Receipt. It is published to the
same authoritative evidence location visible to the operator. A coordinator
may explain the report but cannot rewrite its observations or result.

## Capability-Aware Repair

A failed capability check may return to bounded repair when the repair remains
inside the existing task and mission:

```text
capability_check
  -> capability_regression
  -> building
  -> mechanical_check
  -> critic_review
  -> integrating
  -> capability_check
```

All existing round, time, and cost limits still apply. The repaired integrated
artifact receives fresh implementation checks, criticism where applicable, and
capability evidence.

If repair requires weakening a capability, changing its proof, replacing its
baseline, or narrowing its triggers, the run enters
`mission_amendment_requested` instead.

## Capability Restriction Tripwire

The following changes are automatically classified as
`capability_restriction_candidate` when they affect a critical capability:

- narrowing a tool or API schema;
- removing an action, path, input, or decision option;
- replacing adaptive behavior with a fixed sequence;
- embedding a previously generated answer, payload, or decision in a prompt or
  server-owned plan;
- adding a mandatory fence that prevents otherwise authorized behavior;
- moving product judgment from the declared decision-maker into a controller;
- weakening a positive control, negative control, threshold, trigger, or
  baseline.

The candidate must state the behavior it intends to control and provide direct
evidence that the critical capability remains preserved before the integrated
candidate can be accepted. A bounded integration candidate may be created for
the product-truth probe, but the open restriction tripwire blocks final
acceptance until that evidence passes.

The protocol principle is:

> A constraint introduced to correct unsafe or incorrect behavior must identify
> the observed failure, remain narrowly targeted, and prove that the protected
> capability still works.

Safety boundaries remain valid. This rule prevents safety repair from silently
turning a capable product into a non-capable one.

## Mission Amendment Request

A mission amendment is a stronger subtype of material change. It pauses all
affected work and requires a direct operator decision.

Required technical explanation:

- exact mission fields and capabilities proposed for change;
- evidence that the current contract cannot be satisfied;
- behavioral, architectural, testing, safety, and compatibility impact;
- alternatives considered;
- rollback implications;
- temporary or permanent status.

Required plain-English Operator Impact Statement:

```text
Today the product can...
After this amendment, it will...
The user may lose...
The expected benefit is...
If you decline, the consequence is...
```

Changing a capability's proof, baseline, trigger scope, severity, positive
control, negative control, or provenance requirement counts as a mission
amendment. It cannot be presented as a test correction.

An amendment missing either explanation is invalid. If authorized, the new
Mission Contract records its parent hash, authority basis, reason, and any
required replacement baseline. Rejection leaves the prior mission unchanged.

## Failure Handling

KLP v0.3 fails closed at the claim boundary:

| Condition | Required result |
| --- | --- |
| Missing or invalid Mission Contract | `mission_mismatch` |
| Task bound to stale or unknown mission hash | `mission_mismatch` |
| Triggered capability omitted from task | `mission_mismatch` |
| Required baseline missing or invalid | `capability_unproven` |
| Capability probe unavailable or inconclusive | `capability_unproven` |
| Capability result below its frozen threshold | `capability_regression` |
| Mission weakening proposed | `mission_amendment_requested` |
| Consequential probe lacks authority | Do not run it; record `capability_unproven` |

These states do not assert that the artifact is universally bad. They assert
that KLP lacks authority or evidence to claim mission-preserving completion.

## Required Record Additions

KLP v0.3 adds:

| Record | Required content |
| --- | --- |
| Mission Contract | Mission identity, product outcome, critical capabilities, controls, triggers, baselines, provenance requirements, and amendment authority. |
| Mission Binding Report | Task and mission identities, trigger evaluation, declared impacts, and verifier result. |
| Capability Baseline | Capability, artifact revision, controls, observations, result, limits, and evidence. |
| Capability Report | Before/after comparison, disposition per capability, probe results, and evidence. |
| Mission Amendment Request | Proposed delta, technical explanation, plain-English impact, alternatives, evidence, and requested authority. |

The Final Receipt adds the Mission Contract identity and capability report. A
receipt without them cannot claim conformance to v0.3.

## Offline Lifecycle Proof

The v0.3 release adds an offline `capability-regression` fixture. It uses a
small adaptive-choice application whose core capability requires selecting
different actions for different inputs.

The failing artifact always returns one safe fixed action. Its local shape and
unit checks pass, and a task-scoped critic can accept it. The product-truth
probe uses:

- positive controls requiring distinct correct choices for distinct inputs;
- a negative control that rejects constant output;
- provenance showing whether the result came from input-dependent logic or a
  pre-authored answer.

The fixture must prove:

1. green task checks do not produce completion;
2. the capability gate enters `capability_regression`;
3. one authorized bounded repair restores adaptive behavior;
4. the integrated artifact then receives `preserved` or `improved`;
5. a zero-round repair budget stops correctly;
6. an inconclusive probe produces `capability_unproven`;
7. an undeclared trigger produces `mission_mismatch`;
8. an amendment missing either required explanation is rejected;
9. an authorized amendment preserves parent identity and authority evidence.

The fixture uses no paid provider, network access, live application, or
production mutation.

## Documentation And Adapter Changes

Implementation updates are expected in:

- `PROTOCOL.md`: authority hierarchy, lifecycle, roles, hard rules, amendment,
  capability gate, and completion;
- `AI_AGENT_INTEGRATION.md`: minimum record shape, bootstrap instructions,
  envelopes, handovers, critic output, and capability report;
- `RUNTIME_PROFILES.md`: local, single-host, distributed, and scheduled auditor
  options;
- `SAFETY_AND_LIMITS.md`: probe authority, capability restrictions, and claim
  limits;
- `README.md`: plain-language explanation and v0.3 walkthrough;
- `adapters/hermes-kanban.md`: mission loading, separate execution management,
  capability impact, and direct auditor reporting;
- `examples/capability-regression/`: offline lifecycle fixture and tests.

The existing v0.2 fail-review-repair fixture remains as proof of task-level
mechanics. The new fixture proves mission-level preservation.

## Versioning And Compatibility

This is a protocol-level change and uses `klp-core/v0.3`. Existing v0.2 records
remain valid v0.2 records but cannot claim v0.3 conformance. Implementations may
support both versions during transition.

A v0.2 task can migrate only by creating a Mission Contract, binding a new task
revision to it, and capturing required baselines. Existing evidence may be
referenced when its artifact identity and observation method remain valid.

No migration may silently infer a product mission from old task checks.

## Acceptance Criteria

The v0.3 implementation is acceptable when:

- every v0.3 task references an exact Mission Contract revision;
- changed capability triggers cannot be omitted without a stop;
- critical capability degradation or missing proof prevents completion;
- technical checks and critic approval cannot override a failed capability
  probe;
- capability evidence covers the integrated artifact;
- decision provenance is enforced when declared;
- mission amendments require both technical and plain-English explanations;
- mission revisions preserve identity, parentage, reason, and operator
  authority;
- offline tests demonstrate fail, bounded repair, re-check, stop, and amendment
  behavior;
- documentation explains the system to both implementers and non-technical
  operators;
- KLP continues to authorize no consequential action by itself.

## Implementation Sequence

1. Update the normative protocol and minimum record definitions.
2. Add machine-readable examples for Mission Contract, capability reports, and
   amendment requests.
3. Build the offline capability-regression fixture test-first.
4. Update runtime profiles, safety guidance, and the Hermes adapter.
5. Update the plain-language README and migration guidance.
6. Run both offline lifecycle fixtures and all critic-harness tests.
7. Review the combined v0.3 artifact against this design before publication.
