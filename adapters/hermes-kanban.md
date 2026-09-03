# Hermes Kanban Adapter

Status: optional worked example; Hermes is not required by KLP Core

[Hermes Agent](https://github.com/NousResearch/hermes-agent) includes a durable,
SQLite-backed Kanban system for collaboration between named agent profiles. Its
task graph, workspaces, heartbeats, blocking, retries, verifier tasks, and
synthesis tasks map naturally to KLP concepts.

Refer to the current official
[Hermes Kanban documentation](https://github.com/nousresearch/hermes-agent/blob/main/website/docs/user-guide/features/kanban.md)
before configuring exact commands or options.

## Concept Mapping

| KLP concept | Hermes Kanban concept |
| --- | --- |
| Project boundary | Kanban board |
| Canonical Mission Contract | Separately pinned immutable board artifact with declared digest; never the mutable root task body |
| Authorized, versioned task contract | Root task body and reviewed metadata bound to the canonical Mission Contract identity |
| Execution Coordinator (KLP Coordinator) | Board manager profile that preserves delegation, state, and evidence references |
| Mission Custodian | Separate named profile for critical-capability work; not the Execution Coordinator |
| Capability Auditor | Dependent mechanical verifier profile that publishes observations directly to operator-visible evidence |
| Work unit | Child task |
| Worker identity | Named Hermes profile or assignee |
| Bounded workspace | Task workspace or Git worktree |
| Dependency | Linked parent or prerequisite task |
| Active ownership | Atomic task claim plus heartbeat |
| Worker handover | Completion summary, comments, and evidence references |
| Blocked or material change | Blocked task with a specific reason and authority request |
| Independent critic | Dependent verifier task assigned to another profile |
| Finding disposition | Coordinator comment with direct evidence references |
| Integration owner | Synthesizer task or designated orchestrator profile |
| Final evidence receipt | Root completion summary plus retained evidence references |

## Recommended Graph

```text
pinned immutable Mission Contract artifact
  -> reviewed root task
      -> worker task A ----\
      -> worker task B -----+-> critic/verifier -> integrator -> Capability Auditor -> final review
      -> worker task C ----/
```

The verifier must depend on all relevant worker tasks. The integrator depends
on the relevant verifier, treats the combined result as a new artifact, and
hands its exact revision to the Capability Auditor. The Capability Auditor then
depends on that integrated artifact and records its mechanical result to
operator-visible evidence without Execution Coordinator rewriting. Final review
may close a bounded run only when the capability gate has passed and no blocking
finding or consequential action remains. Board completion does not itself
authorize merge or deployment.

For critical-capability work, use distinct named Hermes profiles for the
Execution Coordinator, Mission Custodian, worker, independent critic, and
Capability Auditor as required by the Protocol. The Mission Custodian must not
implement or troubleshoot the worker code in the same critical run.

## Worker Instructions

Each dispatched worker should receive:

- one judgeable outcome;
- its exact base revision and workspace;
- allowed and protected paths;
- required checks and evidence;
- forbidden actions and side effects;
- round, time, and cost limits;
- the coordinator's delegated decisions and authority boundary;
- the stop conditions from KLP Core.

Use Kanban comments and completion summaries for short facts and durable
references. Keep raw secrets, private logs, and unrelated transcripts out of
task metadata.

## Mission And Capability Controls

At task approval, repair, integration, and final review, Hermes must load the
canonical Mission Contract from the separately pinned immutable artifact. It
must verify `mission_id`, `mission_revision`, and `mission_hash`, then compare
the changed surfaces with capability trigger rules and require every triggered
capability in `affected_capabilities[]`. An undeclared trigger is
`mission_mismatch`, not a discretionary board decision.

The Mission Custodian performs this binding and impact check; the Execution
Coordinator records the result but cannot reinterpret the frozen contract. The
Capability Auditor runs the approved baseline and exact integrated-artifact
probes with their declared controls and decision provenance. Hermes must
prevent board completion when a critical probe fails or is inconclusive. A
missing, unavailable, invalid, or inconclusive probe is
`capability_unproven`; a post-integration result below the frozen accepted
baseline is `capability_regression`.

When satisfying work would require changing a Mission Contract commitment,
Hermes creates a blocked `mission_amendment_requested` task. That task contains
the requested delta, alternatives, evidence, rollback implications, duration,
the required technical explanation, and the required plain-English Operator
Impact Statement. It waits for direct human operator approval of a versioned
Mission Contract revision.

## Kanban Versus Subagent Delegation

Hermes also supports in-process subagent delegation. Use delegation for bounded
reasoning that can return to a parent in one session. Use Kanban for work that
must survive restarts, cross named agent profiles, retain a visible audit trail,
or allow human intervention.

A Kanban worker may use subagents internally, but the durable KLP assignment,
artifact revision, evidence, and final state still belong on the board or in
referenced storage.

## Memory

Hermes supports built-in and external memory providers. Memory and chat can
help a profile recall prior context, but they are advisory only. The immutable
Mission Contract and direct Capability Auditor, verifier, and critic evidence
remain authoritative. A memory result or conversation is not an assignment,
contract, verdict, capability proof, or approval.

## Compatibility Checklist

Before calling a Hermes board KLP-compatible, confirm:

- the Mission Contract is separately pinned, immutable, and loaded at approval,
  repair, integration, and final review;
- the root task preserves an authorized contract identity and delegation;
- the Execution Coordinator and Mission Custodian are separate identities for
  critical-capability work;
- workers use separate identities and bounded workspaces;
- heartbeats and retry limits are configured;
- exact artifact revisions appear in handovers and critic requests;
- every critic finding has an evidence-backed disposition;
- a separate verifier is gated on all relevant workers;
- the integrator treats the combined result as a new artifact before the
  Capability Auditor checks it;
- changed surfaces are compared to capability triggers and all triggered
  capabilities are declared;
- the Capability Auditor publishes direct operator-visible evidence that the
  coordinator cannot rewrite;
- failed or inconclusive critical probes prevent board completion;
- a required Mission Amendment Request records both required explanations;
- blocking and material-change states stop automatic progression;
- no task completion automatically triggers a consequential live action.

Hermes Kanban is currently strongest for multi-profile work on one host. A
distributed fleet requires additional shared-state, queue, identity, and
artifact-storage design beyond this adapter example.
