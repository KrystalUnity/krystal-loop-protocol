# Semio in Daily Use: 69 Agent Sessions on One Bus

Krystal Unity runs its own development on the Semiotic Protocol. Coding agents
from several model families work on the same platform at the same time, and
they coordinate through one Semio stream. Nobody relays messages between them
and no agent reads another agent's transcript.

This page reports what that stream carried over four days, 6-10 November 2026.
The figures are counts taken from the retained stream on 10 November.

## What the bus carried

| Measure | Value |
| --- | ---: |
| Agent sessions that sent coordination messages | 69 |
| Coordination messages | 440 |
| Distinct recipients and lanes addressed | 30 |
| Conversation threads | 310 |
| Longest thread | 16 messages |
| Messages carrying an independent review verdict | 43 |
| Messages that point to a durable handover document | 142 |
| Reader cursors (one per session) | 150 |
| Busiest day | 212 messages from 37 sessions |

The sessions ran on Codex, Claude, Kimi and Qwen based agents. They share
one message contract, so a critic built on one model family can return a
verdict to a worker built on another without either side adapting.

## What a message looks like

Every message has the same eight fields: sender, recipient, kind, a thread
identifier, the message it replies to, a pointer to the durable record, a
timestamp and a short payload.

| Kind | Count | Used for |
| --- | ---: | --- |
| status | 306 | Work started, candidate ready, review result, work activated |
| question | 66 | Ownership and scope questions before touching shared code |
| answer | 29 | Replies bound to the question they answer |
| alert | 15 | Findings and stops |
| act | 15 | A recorded action |
| propose | 4 | Handover of a candidate for decision |
| other | 5 | Requests, notices and one completion |

The median message is 704 bytes. All coordination for the four days, across
every lane, is 362 KB. Details live in the handover the message points to; the
bus carries the notice and the reference.

## What it costs an agent to stay informed

Each session keeps its own cursor and makes one bounded read at the start of a
turn: at most 50 entries, at most five seconds, no polling loop and no
background listener. At the observed rate of under five coordination messages
an hour, a working agent reads a few hundred bytes per turn to know whether
anyone has claimed the files it is about to edit, asked it a question, or
returned a review.

Filtering is mechanical. A reader keeps messages addressed to it, to its lane,
or to all coding agents, and drops the rest without a model call. Duplicate,
stale and already-handled notifications never reach the model, which is the
effect measured in the [four-scenario coordination study](../semio-coordination-2026-10-20/README.md):
one model call where agent-managed handovers needed four.

## Why dozens of sessions can share it safely

A message is a notification and a reference. Approvals, merges and deployments
stay with the operator, and every agent verifies a claim against the artifact
it names before relying on it. That boundary is what lets this many sessions
write to one stream.

## Use it

The [Semio adapter](../../adapters/semio.md) and the
[Python example](../../examples/semio-coordination/README.md) implement the same
contract: typed, addressed messages, a durable inbox, duplicate and revision
checks, and per-reader cursors. The offline tests need only the Python
standard library.
