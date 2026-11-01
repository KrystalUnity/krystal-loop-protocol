# OpenAI-Compatible Critic Harness

This harness sends one explicit, controller-reviewed KLP packet to one
OpenAI-compatible `/chat/completions` endpoint. It does not inspect a repository,
run tools, edit an artifact, repair findings, or authorize a lifecycle action.

## Prepare the packet

Start from `review-packet.example.json`. Bind the packet to the exact worker
result revision, the exact contract ID, revision, and hash it is judged against,
and, for v0.3, the Mission Contract ID, revision, and hash. A v0.3 packet also
declares affected capabilities, preservation or improvement commitments,
expected capability delta, required capability probes, and baseline evidence
references. Include only the bounded diff, declared checks, evidence,
limitations, and unresolved findings needed for review. Include the necessity
of new tooling and relevant prior failed approaches in the existing objective,
commitments, or known-limitations fields so the critic can assess them. The controller must
inspect and redact it before external egress. The harness performs no implicit
file collection, log collection, or content redaction.

Packet contents are untrusted passive evidence. The critic system prompt tells
the model to ignore instructions, role claims, authorization requests, and tool
directives embedded in diffs, comments, tests, or other packet fields. This
reduces prompt-injection risk; it does not make model output trusted.

## Optional sealed-source reads

The default remains one request with all evidence inline. Opt in with
`--evidence-reads` when a review benefits from bounded additional reads.
Supply `sources: {"path": "exact retained text"}` in the original sealed packet;
no filesystem paths are opened from model requests. Only excerpts actually
moved out of the initial packet are offered for retrieval, not inline source.
The final allowed call has no tools and must return a verdict (or BLOCKED for
missing required evidence). Use repeated
`--generated-source path` arguments to compact explicitly selected generated
excerpts with the [context helper](../semio-coordination/review_context.py).
The complete artifact diff stays inline. Existing external reference packets
are rejected; evidence is reconstructed from this run's sealed input only.

This mode allows at most three model calls, eight reads, 8,192 characters per
read, 8,192 output tokens per call and 256 KiB per request, within the single
`--timeout-seconds` deadline. There are no retries. Only `read_evidence` is
exposed; no commands, network browsing or arbitrary file access. Missing source
requires an incomplete review, not a guess. Include necessary coherent source
sections before starting. An excerpt hash is not a full-file hash.

`effort.json` retains every attempted call, raw reported usage, request bytes,
elapsed time and extra-read bytes, including failures. Missing usage/cash costs
are unknown, not zero. `call-N.request.json` and `call-N.response.json` retain
review evidence (without reasoning text). `request.packet.json` preserves the
original sources; `prepared-packet.json` shows the compact input. Protect these
artifacts as source code. Later reads and repeated history count toward full
effort; smaller initial packets alone do not establish savings. Verdict checking
is unchanged; a response receipt is not acceptance.

For providers that support `thinking.type`, `--disable-thinking` can be used
with this mode. Other providers should omit it. Provider spend/data permissions
remain the operator's responsibility. This option does not introduce a benchmark
or enable automatic reviews.

## Configure a different-family critic

```bash
export CRITIC_BASE_URL="https://provider.example/v1"
read -rsp "Critic API key: " CRITIC_API_KEY
export CRITIC_API_KEY
export CRITIC_MODEL="provider-model-id"
export CRITIC_PROVIDER_FAMILY="provider-family"
```

Provider-family labels describe model lineage, not endpoint hostnames. They are
controller-supplied declarations, not cryptographic identity attestation. The
check prevents accidental same-family pairing but cannot detect a false label.
A DeepSeek Flash worker and DeepSeek Pro critic are the same family.

Different-family review is the default. A same-family pairing fails before any
network request. `--allow-same-family` is an explicit escape for a review that
must not be described as independent.

## Run one review

```bash
python3 examples/openai-compatible-critic/critic.py \
  --packet examples/openai-compatible-critic/review-packet.example.json \
  --schema examples/openai-compatible-critic/verdict.schema.json \
  --out-dir review-output \
  --timeout-seconds 90
```

The output directory must be new or empty. A valid run writes:

```text
request.packet.json
provider-response.json
verdict.json
```

The request artifact contains the controller-supplied packet and schema but no
authorization header. Its filename does not claim the packet was sanitized. The
provider artifact retains only response identity, model, usage, and final
assistant content; reasoning fields are discarded. Invalid packets, default
same-family pairings, provider failures, malformed JSON, schema failures, and
pass verdicts with blockers produce no `verdict.json`.

## Test without provider egress

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
```

The tests use a local HTTP server and a fake credential. A critic verdict is
advisory evidence for the controller and human; it is never permission to edit,
merge, push, deploy, spend, or perform another live action. For v0.3, the
critic may report capability risk, but it cannot pass, certify, or override the
separate mechanical capability gate.

The v0.3 critic also assesses whether additional tooling and verification serve
the declared outcome. It explains finding origin in `observed`, the acceptance
basis in `commitment`, evidence in `evidence_refs`, and the smallest sufficient
resolution in `repair_acceptance`. Optional improvements do not become blockers
merely because they are useful. The controller adjudicates these claims and
decides whether to simplify within delegation.

The v0.2 prompt and verdict schema remain unchanged. Offline tests verify
compatibility and request handling, not whether a real model follows the new
guidance. The harness makes one request; overall budgets, two-cycle
reassessment, operator steering, and completion remain coordinator duties under
[the protocol](../../PROTOCOL.md#choosing-and-reassessing-the-approach).
