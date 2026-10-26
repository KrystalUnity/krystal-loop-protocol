# KLP With One Human Operator

You do not need a team of employees. You do need a second agent to check the
worker's result. Start with [Standard](../EXECUTION_PROFILES.md) for an ordinary
bounded task; a solo project can still contain Critical work.

## Ordinary Task: Two Agent Sessions

Example: change explanatory UI copy without changing calculations, persistent
state or protected claims, after checking the actual behavior and mission triggers.

| Identity | Job |
| --- | --- |
| You, the operator | Set the outcome, boundaries and budget; retain decisions outside the task's authority. |
| Agent A, worker/coordinator | Keep one versioned task record, implement, run checks and evidence-adjudicate findings. |
| Agent B, critic | In fresh read-only context, review the exact candidate, relevant source and test evidence; confirm Standard eligibility. |

Agent A may apply bounded repairs, but cannot replace Agent B's review with
self-approval. Review must apply to the final contents, including relevant
repair or integration changes. A confirmed blocker cannot be voted away.
No extra Mission Custodian or Capability Auditor seat is required by Standard.

Use a different model family for Agent B when available. Disclose same-family
review as same-family, not model diversity. Fresh context does not eliminate
correlated model errors. The chosen harness or project may impose stronger
requirements; this example does not override them.

## Critical Task: Preserve the Separate Roles

Example: a save-format migration. Follow [Core](../PROTOCOL.md) in full, including
the accepted baseline and probes against the exact integrated result.

| Identity | Job |
| --- | --- |
| You, the operator | Authorize the bounded task and any consequential actions. |
| Custodian C, a separate agent or you | Protect the frozen mission at the required checkpoints; do not implement or troubleshoot the worker's code on this run. |
| Coordinator A | Manage execution, budgets and evidence decisions. May also implement in the worker role where the project's policy permits. |
| Critic B | Independently review the worker's exact artifact, without editing it. |
| Auditor job D | Mechanically execute approved capability probes and retain direct observations; neither edit the artifact nor accept rewritten results from the coordinator. |

If you act as Mission Custodian, you cannot also be Coordinator or troubleshoot
worker code on that same Critical run. Use a separate custodian agent when you
intend to do that work. The auditor can be a separately identified, non-editing
test runner rather than another LLM; the worker cannot be its own auditor.
Record identities, permissions and evidence references so the separation can
be checked. This is not a requirement for separate human employees.

**Renaming the same session is not independent review.** A worker asking itself
to act as critic, or an execution agent also declaring itself the independent
Mission Custodian, does not satisfy the applicable separation rules.

If the required independent roles or capability proof are unavailable, you
cannot claim Critical conformance or downgrade the task to Standard. Record the
gap and stop affected work. Missing capability evidence uses
[`capability_unproven` and its recovery path](../PROTOCOL.md#recovering-missing-capability-proof);
a missing independent role blocks acceptance until the role is available.

## You Do Not Approve Every Turn

Your standing delegation may authorize implementation, checks, review and repairs
inside the recorded boundaries. The agents can finish that work without a click
per round. They ask when an actual authority boundary, required mission amendment
or exhausted limit demands it, not because one agent handed work to another.

Release remains a [separate gate](../EXECUTION_PROFILES.md#routine-release-gate).
Neither a critic verdict nor a passing probe supplies deployment authority.
