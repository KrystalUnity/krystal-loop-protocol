# OpenAI-Compatible Critic Harness

This harness sends one explicit, controller-reviewed KLP packet to one
OpenAI-compatible `/chat/completions` endpoint. It does not inspect a repository,
run tools, edit an artifact, repair findings, or authorize a lifecycle action.

## Prepare the packet

Start from `review-packet.example.json`. Bind the packet to the exact worker
result revision and include only the bounded diff, declared checks, evidence,
limitations, and unresolved findings needed for review. The controller must
inspect and redact it before external egress. The harness performs no implicit
file collection, log collection, or content redaction.

Packet contents are untrusted passive evidence. The critic system prompt tells
the model to ignore instructions, role claims, authorization requests, and tool
directives embedded in diffs, comments, tests, or other packet fields. This
reduces prompt-injection risk; it does not make model output trusted.

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
merge, push, deploy, spend, or perform another live action.
