# Optional Runtime Profiles

KLP defines operating requirements, not an infrastructure stack. Start with the
smallest durable system that matches the number of agents, hosts, and failure
modes in your project.

## Capability Layers

| Layer | Requirement | Examples |
| --- | --- | --- |
| Authoritative state | Required | Versioned files, SQLite, PostgreSQL |
| Artifact identity | Required | Git commit, content digest, immutable build ID |
| Evidence storage | Required | Repository files, local proof directory, object storage |
| Coordination transport | Optional | Shared database, Redis Streams, NATS, RabbitMQ |
| Retrieval memory | Optional | Full-text search, embeddings, vector database |
| Agent tool adapter | Optional | CLI, MCP server, framework-native tools |

The authoritative state layer owns the canonical Mission Contract, versioned
task contracts, assignments, lifecycle state, finding dispositions, capability
baselines and reports, evidence references, and human decisions. A Mission
Contract is authoritative only when its canonicalization and digest method are
declared. Optional layers may accelerate or present this state but must not
silently replace it.

## Profile A: Local And Simple

Use this for one lead agent and a small number of sequential workers.

```text
Git repository
  + immutable Mission Contract JSON or structured Markdown record
  + Markdown or JSON task records
  + append-only state-events.jsonl
  + local evidence directory
  + normal test/build tools
  + manually invoked offline Capability Auditor
```

No database, message bus, or scheduler is required. Use atomic snapshots,
append-only state events, exact Git revisions or content digests, and a clear
folder convention. The Mission Custodian verifies exact Mission Contract
binding and affected capabilities at approval, repair, integration, and final
review. The Capability Auditor manually runs the approved baseline and
post-integration product-truth probes against the declared artifacts and keeps
its observations with the local evidence. This is enough to learn KLP before
adding infrastructure.

## Profile B: Single-Host Multi-Agent

Use this when several named agents work concurrently on one machine.

```text
SQLite in WAL mode or PostgreSQL
  + immutable Mission Contract snapshots and hashes
  + task/dependency table
  + ownership leases or heartbeats
  + append-only state events
  + evidence files
  + optional local queue or stream
```

The database should enforce atomic assignment and idempotent state changes.
The queue carries notifications; the database remains the durable source of
truth. Separate workspaces or Git worktrees reduce file collisions. This
profile may schedule a Capability Auditor and publish its signed or immutable
observations directly to the operator-facing evidence store. Scheduling is
optional: the scheduled result supplements monitoring and never replaces the
required post-integration capability gate on the exact integrated artifact.

## Profile C: Distributed Fleet

Use this only when workers span machines or failure domains.

```text
Transactional database
  + durable queue
  + immutable artifact/evidence storage
  + immutable shared Mission Contract records and capability reports
  + worker identity and scoped credentials
  + lease expiry and crash recovery
  + centralized observability
```

Add idempotency keys, retry ceilings, dead-letter handling, clock-skew tolerant
leases, and tenant or project isolation. Distributed operation increases the
importance of immutable artifact identity and makes filesystem-only state
insufficient. Give a distributed Capability Auditor only scoped probe
credentials and access to the exact approved artifacts. Shared evidence must be
immutable or append-only and available to the Mission Custodian and operator;
neither a coordinator nor a scheduler may rewrite auditor observations.

## Capability Gate Operation

Every profile preserves the same v0.3 contract. Before work, the Capability
Auditor runs the required controls against the accepted baseline artifact. After
integration, it runs the required controls against the exact integrated
artifact revision and records a disposition for every affected capability.
The Mission Custodian compares changed surfaces with the Mission Contract's
trigger rules at approval, repair, integration, and final review. A missing,
unavailable, invalid, or inconclusive required probe is
`capability_unproven`, not permission to continue.

Local manual operation, optional scheduled monitoring, and distributed shared
operation are deployment choices. They do not change the gate: a critical
capability that is `degraded` or `unproven` blocks `completed`, and scheduled
monitoring never replaces post-integration proof.

## Shared Effort And Review Limits

All profiles use one parent task budget covering planning, tools, reviews and
retries, waiting, repairs, and completion. Child tasks, replacement agents, and
resumed runs recover the remaining budget; they do not receive a fresh allowance.
Elapsed time is measured across the parent task, while resource use aggregates
across children. Use one coordinated review plan when combining KLP with skills
or other frameworks, reusing applicable evidence without omitting mandatory
gates. The coordinator owns approach reassessment and completion as defined in
[the protocol](PROTOCOL.md#choosing-and-reassessing-the-approach).

## Communication Guidance

Agent communication should be short and structured:

- status and heartbeats;
- questions and correlated answers;
- artifact and evidence references;
- blocking findings and stop reasons.

Do not use chat transcripts as the only task ledger. Preserve durable state
outside the conversation so a replacement agent can resume from records rather
than reconstructed memory.

## Vector And Semantic Memory

Vector memory is useful for finding prior decisions, similar repairs, and
relevant evidence across long projects. It is not a safe source of truth.

Recommended design:

```text
canonical files or database
  -> redacted chunks
  -> text/vector index
  -> retrieved context with source references
```

The index must be rebuildable. Retrieval results can inform an agent but cannot
change task state, approve a finding, or authorize a live action. Critical
facts should be verified against canonical records before use.

## MCP And Other Tool Interfaces

MCP can expose KLP task, evidence, and status operations to compatible agents.
Expose narrow tools such as `get_assignment`, `record_handover`,
`submit_finding`, and `request_material_change`. Tool access should be scoped to
the agent's role and assignment.

An MCP call is still only an interface action. Whether it may mutate state or
trigger a live system remains controlled by the underlying authorization and
human decision boundary.
