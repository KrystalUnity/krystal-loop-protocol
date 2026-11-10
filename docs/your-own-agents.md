# Run the Loop With Your Own Agents

`klp run` drives the whole Standard loop for you. This page is for teams wiring
KLP into agents and orchestrators they already have: the starting prompt, the
worker and critic examples, and the offline fixtures that show each stage on
its own. Paths in the prompt are relative to the repository root.

## Start With One Prompt

Give this to the lead agent before a multi-agent build:

```text
Work under Krystal Loop Protocol.
Read EXECUTION_PROFILES.md, select the profile and record why before editing.
For Standard, follow its complete checklist using examples/standard-task.md:
one record, bounded work, relevant checks, independent review and integration.
For Critical, follow PROTOCOL.md in full. Do not downgrade existing gates.
Follow AI_AGENT_INTEGRATION.md and SAFETY_AND_LIMITS.md for context, isolation,
evidence and authority. Reuse checks; do not invent extra process machinery.
Finish when the required proof is met. If proof is missing, preserve the work,
state the exact blocker and smallest next action, then stop affected work.
Keep routine shipping behind EXECUTION_PROFILES.md's routine-release-gate.
No profile grants deployment, spending or publication authority.
Runnable offline references: examples/capability-regression/README.md and
examples/fail-review-repair/README.md. See VERIFY.md for what each proves.
```

KLP does not require a special model, database, vector store, or message bus.
You can start with Git and Markdown files, then add durable coordination when
the project needs it.

## Run a Worker and Critic

`klp run` drives this whole path for you. The included examples show each
stage on its own, for teams wiring KLP into their own agents:

```text
DeepSeek Flash worker
  -> exact revision and deterministic checks
  -> controller-redacted, sealed review packet
  -> different-family read-only critic
  -> evidence-backed finding dispositions
  -> bounded repair or integration
```

Start with the [DeepSeek Codex worker](../examples/deepseek-codex-worker/README.md),
then use the
[OpenAI-compatible critic harness](../examples/openai-compatible-critic/README.md).
The worker launcher uses an isolated Codex profile and a reviewed assignment.
The critic makes one request by default, validates its structured verdict locally,
and cannot edit or authorize any action. Its optional bounded evidence-read mode
can retrieve selected generated source from the sealed packet. The examples do not automatically connect
worker output to critic input; the controller must inspect and redact the
review packet first.

### Review Generated Source

Use the [maintained critic quick-start](../examples/openai-compatible-critic/README.md#review-generated-source)
when a task includes generated code. Supply the exact retained source, keep the
complete diff and required checks, and explicitly select which generated excerpts
may move out of the initial prompt. The runner verifies retained text and gives
the critic bounded reads; it does not let the model browse your filesystem.

Malformed JSON, schema failures and a pass with blocking findings are rejected.
Keep failed receipts; never extract an apparent verdict from a malformed reply.
Count all calls, later reads, repairs and failures using the runner's effort
records, not just the initial packet size. No benchmark is needed to use it.

The harness reviews `klp-core/v0.2` and `klp-core/v0.3` packets for Critical
work. Standard work is reviewed by `klp run`.

## Run the Offline Lifecycle Proof

The [fail-review-repair fixture](../examples/fail-review-repair/README.md) proves a
complete bounded lifecycle without provider egress or model spend:

```bash
output="$(mktemp -d)/klp-fixture"
python3 examples/fail-review-repair/run_fixture.py --out-dir "$output"
python3 -m json.tool "$output/final-receipt.json"
```

It creates a temporary Git project, records a deliberately incomplete worker
revision, captures a failed check, runs the sealed critic harness against a
loopback fake provider, confirms one real finding, refutes one false finding,
applies one authorized repair, and re-checks the integrated artifact. A second
test proves a zero-round repair budget stops instead of overrunning authority.

The [capability-regression fixture](../examples/capability-regression/README.md)
proves the v0.3 product-truth gate. It establishes an accepted baseline,
deliberately regresses an adaptive capability while task checks pass, blocks
completion, repairs within the declared limit, and proves the repaired
integrated artifact. Both lifecycle fixtures run offline.

## Let Software Run the Repetitive Checks

An AI reviewer should judge the evidence, not spend turn after turn launching
the same tests. The optional [capability audit runner](../examples/capability-audit/README.md)
runs approved checks against frozen before-and-after versions, isolates each
execution, and prepares a compact evidence packet for independent review.

The collector makes no model calls. It retains failed checks and incomplete
evidence instead of converting them into a green result. Use it when a task
already needs a capability audit; ordinary Standard work stays lightweight.

The runner has been exercised on a real, asset-heavy game repository: 42 probe
executions including preflight and a bounded correction. See the
[validation note](../examples/capability-audit/VALIDATION.md). Linux, Python, Git
and Bubblewrap are required.

## What This Prevents

| Common agent failure | KLP response |
| --- | --- |
| Two agents edit the same shared file. | Give each worker an explicit file and action boundary. |
| A worker says its own work is complete. | Separate factual handover from independent acceptance. |
| A critic reviews an outdated build. | Bind every verdict to an exact artifact revision. |
| A critic confidently reports a false problem. | Confirm or refute every finding with direct evidence. |
| Agents keep looping without improvement. | Stop on repeated findings, exhausted budgets, or a plateau. |
| New tooling creates more work than the requested change. | Reassess whether the tooling is necessary; simplify the approach inside delegation. |
| Unit changes pass but break when combined. | Review integration as a new artifact. |
| A test or agent message is treated as permission to deploy. | Keep live actions behind an explicit human decision. |
