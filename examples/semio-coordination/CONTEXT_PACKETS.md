# Compact Context Packets

Compact context packets are an optional preparation method for bounded KLP work. They select the smallest reviewed set of source material needed for a specific assignment while preserving the complete Mission and Task Contracts. This guide does not change KLP rules, versions, dependencies, runtime behavior, authority, or automatic execution. It does not run automatically.

## Required packet contents

A packet must retain the exact mission and task identity, including mission ID, revision, hash, contract identity, authority, allowed and protected paths, forbidden actions, dependencies, required capability probes, checks, evidence references, unresolved findings, repair limits, time and cost limits, and stop rules. The worker must recover these from authoritative durable storage, not rely on conversational memory. Required acceptance evidence must not be omitted merely because context is compact.

A small manifest can document the selection:

```json
{
  "base_revision": "b2449906af604eb203944b3332bb163c5c7c58dc",
  "included": ["AI_AGENT_INTEGRATION.md", "adapters/semio.md"],
  "omitted": ["PROTOCOL.md", "runtime files"],
  "hashes": {
    "AI_AGENT_INTEGRATION.md": "sha256:ILLUSTRATIVE_PLACEHOLDER",
    "adapters/semio.md": "sha256:ILLUSTRATIVE_PLACEHOLDER"
  },
  "role": "worker",
  "selection_reason": "These reviewed documents cover the applicable contracts, authority boundaries, evidence, and adapter behavior."
}
```

The hashes above are illustrative placeholders. They do not verify content. When a hash or revision matters, check it against the source and record the actual result. The packet should state why each included item is sufficient and identify omitted material whose absence could affect the task.

## Controlled additional reads

Additional reads are allowed only when the assignment permits them. First check the source revision and, where required, the file hash. Record the number of bytes read and the purpose of each read. Keep cumulative prompt, input, output, cached-token, latency, and monetary accounting; an additional read is not free. Stop and report when evidence is genuinely missing, contradictory, stale, or wider than the approved assignment. A transport reference, message, filename, or hash does not confer permission to read, execute, amend, or deploy anything.

Accounting must include worker usage, additional reads, repairs, critic usage, retries, and failures. Separate prompt bytes from input and output tokens, and separate cached tokens, latency, and monetary cost. If coordinator usage is not exposed, report it as unavailable rather than zero. Failed attempts remain part of the record.

## What earlier evidence shows

In the prior controlled source-review pilot, six source-review calls covered three paired cases using full and compact context. Each mode classified 12 of 12 obligations correctly, for 24 of 24 combined across both modes. The full packets were 194037 bytes and the compact packets 87948 bytes, a reported 54.67% reduction. Reported input tokens were 91017 versus 68601, a 24.63% reduction; cached input was 30720 for each mode. Compact output was 1013 tokens versus 863 for full. The pilot was synthetic, source-only, and used one model/settings configuration. It did not demonstrate universal equivalence, latency improvement, cash savings, coding productivity, or authoring quality.

## Review and handover

The same assignment should be used for compact and full arms, with the compact candidate selected before results. A worker reports the exact artifact revision, factual changes, checks run, evidence references, risks, failures, retries, and limitations. It must not self-accept, claim preservation, or replace an independent critic. The coordinator still performs the declared mechanical and capability checks, and an independent critic reviews the exact candidate. Acceptance remains outside worker authority and requires the required evidence, including capability results and final finding dispositions.

For the optional coordination example, see the [Semio adapter boundary](../../adapters/semio.md) and the [Semio coordination example](README.md).
