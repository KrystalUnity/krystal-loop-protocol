# KLP Core Protocol

Status: provisional public profile

Version: 0.2 draft

## Purpose

KLP Core defines the minimum operating discipline for bounded, reviewable
multi-agent project work. It is provider-neutral and transport-neutral.

The protocol separates four different claims:

1. a bounded task was authorized by an explicit contract or standing delegation;
2. a worker produced an artifact;
3. checks and an independent critic evaluated that artifact;
4. a person separately authorized any consequential action that remained.

No earlier claim implies a later one.

## Roles

| Role | Responsibility |
| --- | --- |
| Human operator | Defines authority boundaries and makes consequential lifecycle decisions. |
| Coordinator | Preserves the task contract and delegation, assigns work, adjudicates findings, tracks state, and integrates evidence. |
| Worker | Produces one bounded outcome and a factual handover. |
| Verifier | Runs deterministic checks and captures direct evidence. |
| Critic | Independently judges one exact artifact revision without modifying it. |
| Integrator | Combines accepted units and owns verification of the combined result. |

One person or agent may hold several roles at different times, but a worker
must not act as the independent critic of the same artifact.

## Core Lifecycle

```text
draft
  -> approved
  -> assigned
  -> building
  -> mechanical_check
  -> critic_review
  -> accepted_unit
  -> integrating
  -> final_review
  -> completed
```

Repair returns `critic_review -> needs_fixes -> building`.
Use `ready_for_authority_decision` instead of `completed` only when a material
change or consequential action remains. Normal bounded repair rounds do not
require repeated human approval.

First-class stop states are:

- `blocked`: a dependency, capability, or required proof is missing;
- `material_change`: the approved objective or boundary would need to change;
- `plateau`: blocking findings are recurring without measurable progress;
- `budget_exhausted`: a declared time, cost, or round limit was reached;
- `safety_stop`: a secret, destructive action, authority boundary, or other
  hard guard was crossed;
- `accepted_with_limitations`: the artifact is usable only with recorded gaps.

## Required Records

KLP implementations may combine records, but must preserve these facts:

| Record | Required content |
| --- | --- |
| Task contract | Contract ID, revision, parent identity, objective, authorized scope, delegation, forbidden actions, checks, evidence, measured limits, and stops. |
| Work-unit assignment | Outcome, owner, exact base revision, allowed paths, dependencies, and limits. |
| Worker handover | Exact result revision, factual changes, check results, evidence references, and open concerns. |
| Evidence report | Commands or observations, results, timestamps, artifact identity, and data-handling status. |
| Critic verdict | Exact reviewed revision, commitment assessments, findings, evidence references, and next action. |
| Finding disposition | Finding ID, `confirmed`, `refuted`, or `unresolved` status, artifact revision, rationale, and direct evidence references. |
| State event | Append-only sequence, previous state, new state, reason, actor, timestamp, contract revision, artifact revision, and supporting evidence. |
| Invalidation receipt | Prior contract or evidence identity, replacement identity, causal evidence, authority basis, and reason. |
| Final receipt | Supported claims, limitations, integration result, unresolved findings, and human decisions still required. |

## Hard Rules

1. An identified, authorized task contract must exist before implementation begins.
2. Every worker must have an explicit outcome and file/action boundary.
3. A worker handover reports facts and cannot issue its own acceptance verdict.
4. Deterministic checks run before model-based criticism whenever such checks
   are available.
5. A critic must be independent, read-only, and bound to the exact artifact
   revision it judges.
6. Every critic finding must be confirmed, refuted, or left unresolved using
   direct evidence. An unresolved blocking finding prevents acceptance.
7. New paths, dependencies, side effects, architecture, or acceptance criteria
   are material changes and stop execution for human review.
8. Repair loops have declared round, time, and cost limits.
9. Integration is a new artifact and requires its own relevant checks.
10. No KLP record, agent, critic, test, or message can authorize a live action.
11. Contract revisions and invalidations preserve the prior identity, causal
    evidence, and authority basis instead of silently replacing history.

## Contract Identity And Delegation

Every contract needs a stable ID and revision identity. A Git revision, content
digest, or immutable record ID is sufficient when its canonicalization method
is declared. A revised contract records its parent identity and reason.

A contract may give the coordinator standing authority for bounded operations
such as running declared checks, invalidating evidence made stale by a new
artifact revision, adjudicating findings with direct evidence, and applying
repairs inside frozen scope and limits. That delegation avoids a human approval
click on every normal repair round.

Delegation cannot silently change the objective, acceptance criteria, allowed
paths, side effects, or resource ceilings. Correcting a test implementation so
it matches frozen criteria may be delegated; changing the criteria themselves
is a material change.

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

A material change includes a proposed alteration to the objective, accepted
plan, scope, architecture boundary, authority, external side effects, data
classification, rollback needs, or resource ceiling.

When a material change is discovered:

1. stop affected work;
2. record the proposed delta and its impact;
3. preserve the current artifact and evidence;
4. request human review;
5. resume only from a newly authorized task contract revision.

## Completion

A KLP run is complete when declared acceptance criteria are supported by
evidence, every critic finding has a disposition, no blocking finding remains,
the integrated result has been checked, limits are measured, and limitations
are recorded. It may reach this state without a per-round human click.

If merge, release, deployment, spending, credential changes, customer contact,
or production mutation remains, record `ready_for_authority_decision` and list
the exact decisions required. Neither status authorizes those actions by
itself.
