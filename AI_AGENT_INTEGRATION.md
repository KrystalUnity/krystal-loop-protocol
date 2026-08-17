# AI Agent Integration Guide

This guide tells an AI agent, orchestrator, or agent framework how to operate
under KLP Core without depending on a particular model or tool stack.

## Required Capabilities

An implementation is KLP-compatible when it can:

- preserve a human-approved task contract;
- assign bounded work units with explicit owners and paths;
- identify the exact base and result artifact revisions;
- run or record deterministic checks;
- store direct evidence and reference it from findings;
- separate worker and critic identities for the same artifact;
- represent stops, repairs, dependencies, and limitations;
- re-check the integrated artifact;
- leave live actions behind a human-controlled decision point.

Persistent memory, vector search, MCP, Redis, a relational database, and a
specific model provider are optional.

## Agent Bootstrap Instructions

An agent beginning a KLP task should follow this order:

1. Read the task contract and current state from durable storage.
2. Confirm the assigned work unit, exact base revision, allowed paths, protected
   paths, dependencies, forbidden actions, checks, evidence, and budget.
3. Stop before editing if the assignment is missing, contradictory, stale, or
   wider than the approved task.
4. Work only inside the assignment boundary.
5. Run the declared checks and capture exact results.
6. Return a factual handover tied to the result revision.
7. Do not declare your own artifact accepted.

Critics must start from fresh read-only context containing the task contract,
exact artifact revision, check results, direct evidence, and unresolved prior
findings. A critic must not edit the artifact it reviews.

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
   [`critic.py`](examples/openai-compatible-critic/critic.py) with
   `--require-independent`.
6. Validate the critic artifacts and present the evidence to the human
   decision-maker.

The worker configuration points Codex at DeepSeek's OpenAI-compatible endpoint,
but the endpoint is only the inference engine. The assignment, sandbox,
deterministic checks, sealed evidence, critic separation, and human authority
remain outside the model. The critic harness likewise accepts any compatible
`/chat/completions` endpoint through environment variables; it makes one
request and performs no retry, repair, merge, push, or deployment.

Do not feed a repository, credentials, private logs, or unreviewed context to
the critic. The controller owns packet construction and redaction. A valid
`verdict.json` is evidence, not permission.

## Minimum Record Shape

Record formats may vary, but an agent must be able to recover these fields:

```text
task_id
unit_id
state
objective
commitments[]
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
round_limit
time_limit
cost_limit
human_decisions_required[]
```

Omitting a field is acceptable only when the field is inapplicable and the
record says why. Empty evidence must not be presented as successful evidence.

## Generic Coordination Envelope

KLP does not require a message bus. When agents communicate through one, the
transport should preserve an envelope similar to:

```json
{
  "protocol": "klp-core/v0.1",
  "message_id": "msg-unique-id",
  "task_id": "task-example",
  "unit_id": "unit-parser",
  "from": "worker-parser",
  "to": "coordinator",
  "kind": "status",
  "correlation_id": "question-or-flow-id",
  "in_reply_to": null,
  "artifact_revision": "revision-or-digest",
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
5. What remains uncertain or blocked?

Avoid persuasive completion language, hidden reasoning, raw secrets, and
unbounded logs.

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

## Stop Behavior

An agent must stop and report rather than improvise when:

- the requested change exceeds allowed paths or actions;
- a required dependency or credential is unavailable;
- the base artifact changed beneath the assignment;
- a deterministic check fails and no bounded repair remains;
- the same blocking finding recurs to the declared plateau limit;
- cost, time, or round budget is exhausted;
- continuing would require a live or destructive action not explicitly
  approved by a person.

## Integration Checklist

Before presenting a combined result to a human:

- verify every accepted unit revision is the one integrated;
- inspect shared contracts and overlapping behavior;
- run relevant unit and integration checks again;
- have a fresh critic review the combined artifact when risk warrants it;
- record unresolved limitations and missing evidence;
- list every consequential action that still requires a human decision.
