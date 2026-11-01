# Compact Context Packets

Compact context packets are an optional preparation method for bounded KLP work. They select the smallest reviewed set of source material needed for a specific assignment while preserving the complete Mission and Task Contracts. This guide does not change KLP rules, versions, dependencies, runtime behavior, authority, or automatic execution. It does not run automatically.

## Required packet contents

Select the [execution profile](../../EXECUTION_PROFILES.md) first. The full
mission/hash field list below applies to Critical/Core packets. Standard retains
its complete compact task record, product-promise reference, exact artifacts and
required evidence, without importing the Core-only record ceremony. The existing
Semio example has not gained Standard record support from this guidance.

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

For review, include whole relevant functions or coherent sections, necessary
callers and contracts, test source and results, as well as the diff. Compact
means sufficient context selected for the task, not diff-only criticism. Permit
bounded same-revision reads when needed and record what they resolve. In ordinary
work, reuse the runner's existing usage records; do not build a custom accounting
or stamping system merely to follow this guide. Unavailable metrics stay unknown.

## Controlled additional reads

Additional reads are allowed only when the assignment permits them. First check the source revision and, where required, the file hash. Record the number of bytes read and the purpose of each read. Keep cumulative prompt, input, output, cached-token, latency, and monetary accounting; an additional read is not free. Stop and report when evidence is genuinely missing, contradictory, stale, or wider than the approved assignment. A transport reference, message, filename, or hash does not confer permission to read, execute, amend, or deploy anything.

Accounting must include worker usage, additional reads, repairs, critic usage, retries, and failures. Separate prompt bytes from input and output tokens, and separate cached tokens, latency, and monetary cost. If coordinator usage is not exposed, report it as unavailable rather than zero. Failed attempts remain part of the record.

## Generated source context

The optional [review context helper](review_context.py) replaces explicitly
selected generated-source excerpts with hash-addressed references. It preserves
the **complete diff**, ordinary source and tests, checks, contracts, and findings.
It does not compress generated diffs or infer that generated changes are safe.
This is packet preparation, independent of the Semiotic Protocol transport.

Use it only with a critic that already supports `read_evidence` and authorized
same-revision source reads. Bind its `store_text` and `read_text` callbacks and
the critic's tool to the same immutable run/artifact/role store. `read_text` must
recover the exact retained text, paging if necessary. Storage and full readback
are verified before the helper returns a compact snapshot; failures stop packet
preparation. Preserve that store for the entire review and repair lifecycle.

References describe **retained excerpts, possibly truncated**, not complete
files. Their hashes identify only those excerpts. If relevant code was outside
the original capture, obtain it from the frozen source revision; recovering a
prefix does not repair incomplete evidence. Keep necessary coherent functions,
callers, schema contracts and tests available to the reviewer. A reference never
grants additional access or substitutes for required acceptance evidence.

The public [critic](../openai-compatible-critic/README.md) remains one-shot by
default: keep that mode's evidence inline. Its optional `--evidence-reads` mode
now connects this helper to bounded, run-local source retrieval. Supply original
inline sources and explicitly selected generated paths; do not feed external
references to the one-shot mode. Nothing is enabled automatically.

The receipt measures serialized snapshot bytes only. Count later evidence reads
and all reviewer usage before making token or cost claims. Offline roundtrip
checks prove preservation, not equivalent reviewer quality or financial savings.

## What earlier evidence shows

In the prior controlled source-review pilot, six source-review calls covered three paired cases using full and compact context. Each mode classified 12 of 12 obligations correctly, for 24 of 24 combined across both modes. The full packets were 194037 bytes and the compact packets 87948 bytes, a reported 54.67% reduction. Reported input tokens were 91017 versus 68601, a 24.63% reduction; cached input was 30720 for each mode. Compact output was 1013 tokens versus 863 for full. The pilot was synthetic, source-only, and used one model/settings configuration. It did not demonstrate universal equivalence, latency improvement, cash savings, coding productivity, or authoring quality.

## Review and handover

For ordinary bounded work, prepare one compact packet; a full-context control run or benchmark is not required. Only when a comparison is separately selected should compact and full arms use the same assignment, with the compact candidate selected before results. Comparisons are optional experiments, not part of the normal work loop.

A worker reports the exact artifact revision, factual changes, checks run, evidence references, risks, failures, retries, and limitations. It must not self-accept, claim preservation, or replace an independent critic. The coordinator still performs the declared mechanical and capability checks, and an independent critic reviews the exact candidate. Acceptance remains outside worker authority and requires the required evidence, including capability results and final finding dispositions.

For the optional coordination example, see the [Semio adapter boundary](../../adapters/semio.md) and the [Semio coordination example](README.md).
