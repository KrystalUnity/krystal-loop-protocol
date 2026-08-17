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
| Project or mission boundary | Kanban board |
| Authorized, versioned task contract | Root task body and reviewed metadata |
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
reviewed root task
  -> worker task A ----\
  -> worker task B -----+-> verifier task -> synthesizer task
  -> worker task C ----/
```

The verifier must depend on all relevant worker tasks. The synthesizer depends
on the verifier and treats the combined result as a new artifact. It may close
a bounded run when no blocking finding or consequential action remains. Board
completion does not itself authorize merge or deployment.

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

## Kanban Versus Subagent Delegation

Hermes also supports in-process subagent delegation. Use delegation for bounded
reasoning that can return to a parent in one session. Use Kanban for work that
must survive restarts, cross named agent profiles, retain a visible audit trail,
or allow human intervention.

A Kanban worker may use subagents internally, but the durable KLP assignment,
artifact revision, evidence, and final state still belong on the board or in
referenced storage.

## Memory

Hermes supports built-in and external memory providers. Memory can help a
profile recall prior context, but KLP task state and evidence must remain in the
Kanban database and referenced artifacts. A memory result is advisory context,
not an assignment, verdict, or approval.

## Compatibility Checklist

Before calling a Hermes board KLP-compatible, confirm:

- the root task preserves an authorized contract identity and delegation;
- workers use separate identities and bounded workspaces;
- heartbeats and retry limits are configured;
- exact artifact revisions appear in handovers and critic requests;
- every critic finding has an evidence-backed disposition;
- a separate verifier is gated on all relevant workers;
- the synthesizer re-checks the combined artifact;
- blocking and material-change states stop automatic progression;
- no task completion automatically triggers a consequential live action.

Hermes Kanban is currently strongest for multi-profile work on one host. A
distributed fleet requires additional shared-state, queue, identity, and
artifact-storage design beyond this adapter example.
