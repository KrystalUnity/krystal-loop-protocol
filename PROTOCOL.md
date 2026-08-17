# KLP Core Protocol

Status: provisional public profile

Version: 0.1 draft

## Purpose

KLP Core defines the minimum operating discipline for bounded, reviewable
multi-agent project work. It is provider-neutral and transport-neutral.

The protocol separates four different claims:

1. a human approved a bounded task;
2. a worker produced an artifact;
3. checks and an independent critic evaluated that artifact;
4. a human separately decided whether to take a consequential action.

No earlier claim implies a later one.

## Roles

| Role | Responsibility |
| --- | --- |
| Human operator | Approves scope and makes consequential lifecycle decisions. |
| Coordinator | Preserves the task contract, assigns work, tracks state, and integrates evidence. |
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
  -> ready_for_human_decision
```

Repair returns `critic_review -> needs_fixes -> building`.

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
| Task contract | Objective, approved plan, scope, forbidden actions, checks, evidence, budget, and stops. |
| Work-unit assignment | Outcome, owner, exact base revision, allowed paths, dependencies, and limits. |
| Worker handover | Exact result revision, factual changes, check results, evidence references, and open concerns. |
| Evidence report | Commands or observations, results, timestamps, artifact identity, and data-handling status. |
| Critic verdict | Exact reviewed revision, commitment assessments, findings, evidence references, and next action. |
| State event | Previous state, new state, reason, actor, timestamp, and supporting evidence. |
| Final receipt | Supported claims, limitations, integration result, unresolved findings, and human decisions still required. |

## Hard Rules

1. The task contract must exist before implementation begins.
2. Every worker must have an explicit outcome and file/action boundary.
3. A worker handover reports facts and cannot issue its own acceptance verdict.
4. Deterministic checks run before model-based criticism whenever such checks
   are available.
5. A critic must be independent, read-only, and bound to the exact artifact
   revision it judges.
6. Open blocking findings prevent acceptance.
7. New paths, dependencies, side effects, architecture, or acceptance criteria
   are material changes and stop execution for human review.
8. Repair loops have declared round, time, and cost limits.
9. Integration is a new artifact and requires its own relevant checks.
10. No KLP record, agent, critic, test, or message can authorize a live action.

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
5. resume only from a newly approved task contract or revision.

## Completion

A KLP run is ready for human consideration when declared acceptance criteria
are supported by evidence, no blocking findings remain, the integrated result
has been checked, and limitations are recorded.

That status does not itself authorize merge, release, deployment, spending,
credential changes, customer contact, or production mutation.
