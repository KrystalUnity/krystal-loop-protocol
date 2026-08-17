# DeepSeek Worker And Independent Critic Examples Design

**Date:** 2026-08-17

**Status:** Approved design awaiting implementation plan

## Purpose

Add a small, runnable demonstration of the complete Krystal Loop Protocol
worker-to-critic path. The examples must show how a lower-cost model becomes a
bounded coding worker and how a separate, read-only model reviews the exact
result without gaining authority to repair, merge, push, or deploy it.

The examples teach portable mechanics. They must not publish Krystal Unity
paths, credentials, model-routing infrastructure, mission data, Redis/Nexus
topology, or private operating procedures.

## Scope

The public addition contains:

1. a sanitized DeepSeek-backed Codex worker profile and launcher;
2. an example bounded assignment and factual worker handover;
3. a provider-neutral OpenAI-compatible critic harness;
4. a sealed review-packet example and a closed critic-verdict schema;
5. local tests using a fake HTTP provider;
6. README links and a short explanation of model routing versus authority.

The addition does not contain a scheduler, queue, database, vector store,
automatic repair loop, deployment integration, hosted service, API key, or
live provider smoke.

## Alternatives Considered

### Documentation snippets only

This is too weak. It tells readers which environment variables exist but does
not prove isolation, packet validation, or critic output handling.

### Full multi-agent orchestrator

This is too broad for KLP Core's first executable example. It would make a
queue, database, or agent framework appear mandatory and would obscure the
protocol boundary.

### Two small runnable examples

Selected. A worker launcher and sealed critic harness demonstrate the complete
control pattern while remaining understandable and independently reusable.

## Repository Shape

```text
examples/
  deepseek-codex-worker/
    README.md
    config.toml.example
    instructions.md
    run.sh
    assignment.example.md
    expected-handover.json
  openai-compatible-critic/
    README.md
    critic.py
    review-packet.example.json
    verdict.schema.json
    tests/
      test_critic.py
```

The root `README.md` links both examples and explains that the endpoint chooses
where inference runs; the KLP task contract and launcher determine what the
worker may do.

## DeepSeek Codex Worker

The profile uses a separate `CODEX_HOME` and these public settings:

```toml
model_provider = "deepseek"
model = "deepseek-v4-flash"
approval_policy = "never"
sandbox_mode = "workspace-write"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com"
env_key = "DEEPSEEK_API_KEY"
wire_api = "responses"

[sandbox_workspace_write]
network_access = false
```

The launcher:

- requires `codex` on `PATH`;
- requires `DEEPSEEK_API_KEY` to already exist in the environment;
- never reads `.env` or another credential file;
- creates or uses only the example's isolated Codex home;
- requires the caller to select the mission workspace explicitly;
- invokes one `codex exec` process with the bounded assignment;
- does not commit, push, launch another agent, or run a critic.

The standing instructions prohibit Git operations, credential access,
production actions, nested agents, additional model providers, edits outside
the assignment allow-list, and undeclared tests. The worker reports changed
files, declared check results, limitations, and stop reason. It does not emit
an acceptance verdict.

## Sealed Critic Harness

`critic.py` is a Python standard-library command. It receives:

```text
--packet <review-packet.json>
--schema <verdict.schema.json>
--out-dir <empty-or-new-output-directory>
--timeout-seconds <positive-number, default 90>
--require-independent
```

Provider configuration comes only from:

```text
CRITIC_BASE_URL
CRITIC_API_KEY
CRITIC_MODEL
CRITIC_PROVIDER_FAMILY
```

The harness appends `/chat/completions` to `CRITIC_BASE_URL`, submits one
non-streaming request, and performs no automatic retry. It never prints or
writes `CRITIC_API_KEY`.

### Review packet

The packet is explicit input, not an implicit repository crawl. It contains:

- protocol version and task identifier;
- objective and commitments;
- worker provider family;
- exact base and result revisions;
- changed-file list and bounded artifact diff;
- deterministic check results;
- direct evidence references or excerpts;
- known limitations and unresolved findings.

The harness rejects a packet with missing required fields, blank revisions,
no commitments, no check evidence, or a serialized size above 256 KiB. The
caller is responsible for redacting the packet before egress. The harness does
not discover files, logs, environment variables, or Git history on its own.

### Independence

With `--require-independent`, the harness compares the normalized worker and
critic provider-family labels before making a network request. Equal labels
fail closed. A DeepSeek Flash worker reviewed by DeepSeek Pro may be useful as
a same-family review, but it must not be described as independent.

### Critic prompt and verdict

The critic receives only the sealed packet, the verdict schema, and a fixed
read-only instruction. It is told to assess the declared commitments and
evidence, avoid speculative scope, and return JSON only.

The verdict vocabulary is:

```text
PASS
PASS_WITH_NONBLOCKING_FINDINGS
NEEDS_FIXES
BLOCKED
ESCALATE
```

Each finding records its identifier, severity, blocking flag, affected
commitment, observed behavior, expected behavior, evidence references, and
repair acceptance criterion. An open blocking finding cannot coexist with a
pass verdict.

The output directory contains:

```text
request.redacted.json
provider-response.json
verdict.json
```

`request.redacted.json` contains provider/model labels and the packet but no
authorization header. `provider-response.json` retains request identifiers,
model, usage when supplied, and final assistant content; reasoning fields are
discarded. `verdict.json` is the parsed and validated final judgment.
