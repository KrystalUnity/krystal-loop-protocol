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

The authoritative state layer owns versioned task contracts, assignments,
lifecycle state, finding dispositions, evidence references, and human
decisions. Optional layers may accelerate or present that state but must not
silently replace it.

## Profile A: Local And Simple

Use this for one lead agent and a small number of sequential workers.

```text
Git repository
  + Markdown or JSON task records
  + append-only state-events.jsonl
  + local evidence directory
  + normal test/build tools
```

No database or message bus is required. Use atomic snapshots, append-only state
events, exact Git revisions or content digests, and a clear folder convention.
This is enough to learn KLP before adding infrastructure.

## Profile B: Single-Host Multi-Agent

Use this when several named agents work concurrently on one machine.

```text
SQLite in WAL mode or PostgreSQL
  + task/dependency table
  + ownership leases or heartbeats
  + append-only state events
  + evidence files
  + optional local queue or stream
```

The database should enforce atomic assignment and idempotent state changes.
The queue carries notifications; the database remains the durable source of
truth. Separate workspaces or Git worktrees reduce file collisions.

## Profile C: Distributed Fleet

Use this only when workers span machines or failure domains.

```text
Transactional database
  + durable queue
  + immutable artifact/evidence storage
  + worker identity and scoped credentials
  + lease expiry and crash recovery
  + centralized observability
```

Add idempotency keys, retry ceilings, dead-letter handling, clock-skew tolerant
leases, and tenant or project isolation. Distributed operation increases the
importance of immutable artifact identity and makes filesystem-only state
insufficient.

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
