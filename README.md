# Krystal Loop Protocol

![Krystal Loop Protocol](assets/krystal-loop-protocol-banner.jpg)

Hand the coding to a fast, low-cost model. Have a frontier model check the
exact result. Keep the decision yourself.

Krystal Loop Protocol (KLP) is an operating pattern for building with AI
agents: bounded work, checks that actually run, independent review of the exact
result, and a hard limit on time, cost and repairs. It ships with a one-command
runner and a public benchmark you can rerun.

## Results

**66 real feature tasks in Click, Jinja and dirty-equals, each graded by tests
the models never see.**

| | Tasks solved | Cost per task | Whole benchmark |
| --- | ---: | ---: | ---: |
| Frontier model working alone | @@F_SOLVED@@ of 66 | $@@F_PER_TASK@@ | $@@F_TOTAL@@ |
| **KLP Standard**: low-cost worker, frontier critic | **@@K_SOLVED@@ of 66** | **$@@K_PER_TASK@@** | **$@@K_TOTAL@@** |

@@HEADLINE@@

[Results and receipts](case-studies/feature-benchmark-2026-11-10/README.md) ·
[Run the benchmark yourself](bench/README.md) ·
[All measurements](EVIDENCE.md)

## Start Here

**Ordinary coding task? Use Standard, in one command.**

```bash
pipx install git+https://github.com/KrystalUnity/krystal-loop-protocol
export DEEPSEEK_API_KEY=...  OPENAI_API_KEY=...

cd your-repository
klp init
klp run "Fix the pagination bug in list_jobs" --check "python -m pytest -q tests/test_queue.py"
```

1. **A worker builds the change** in a sandboxed copy of your repository. Your
   working tree is untouched.
2. **The runner executes your checks.** A check that did not run is not a pass.
3. **An independent critic reviews the exact result.** It is a different model
   family from the worker and sees the task, the diff and the check output.
4. **Findings are settled by evidence.** Every blocking finding comes with a
   probe test. A probe that fails confirms the finding; a probe that passes
   discards it.
5. **Confirmed findings get one bounded repair,** which is checked and reviewed
   again.
6. **You get a patch, a plain-English receipt and the decision.** Merging,
   pushing and deploying stay with you.

On the [public challenge task](https://github.com/KrystalUnity/klp-public-challenge)
this takes 16 seconds and costs $0.012, with all 17 acceptance checks passing.

`klp init` writes your model routes and limits to `~/.config/klp/config.json`.
Any OpenAI-compatible endpoint works, including a local model. Requirements:
Linux or WSL, Python 3.11+, Git and bubblewrap.

Running the loop by hand or with your own agents? Standard is also a single
[task record](examples/standard-task.md): one worker, one separate reviewer and
Git. [Working solo? Here is the role setup](examples/solo-operator.md).

**Changing saves, security, money or a protected core capability?** Use the
[Critical path](EXECUTION_PROFILES.md#critical-preserve-the-existing-core-gate).
It proves the product still does its main job before and after the change.
List your project's critical triggers in `klp.json` and the critic checks every
change against them. Read [profile selection](EXECUTION_PROFILES.md#select-before-editing)
first; a Critical run stays Critical.

## Try the Demo

**Rerun the benchmark.** About two minutes of setup, no Docker:

```bash
python3 -m bench.features prepare --work ~/klp-bench
python3 -m bench.features run --work ~/klp-bench --cap 25
```

See the [benchmark guide](bench/README.md) for the arms, the tasks and the
receipts you get back.

**Watch KLP catch a broken product even when ordinary tests pass.** No API keys
needed. From a checkout, with Python 3.12+, Git and a POSIX shell:

```bash
output="$(mktemp -d)/klp-demo"
python3 examples/capability-regression/run_fixture.py --out-dir "$output" &&
python3 -m json.tool "$output/final-receipt.json"
```

The demo makes a tiny program stop responding correctly to different inputs.
Its ordinary checks stay green. The capability gate catches the regression,
blocks acceptance, then verifies one repair. The receipt's `capability_report`
reads `before: passed`, `intermediate: failed`, `after: passed`.

**[Verify it yourself](VERIFY.md):** recompute every published figure from the
included receipts and run the offline checks.

## What You Gain

- **Frontier-level checking at low-cost-model prices.** The expensive model
  reads one compact review packet per task; the low-cost model does the many
  turns of reading, editing and testing.
- **Findings you can trust.** A reviewer's opinion does not start a repair. A
  failing probe does, and the receipt shows which findings were confirmed,
  which were refuted and which were closed.
- **Less repeated explanation.** Each agent gets the material for its
  assignment. Compact packets cut reported input tokens by 21% on a real
  documentation assignment with the same review outcome.
- **Agents that coordinate themselves.** With the optional Semio adapter,
  duplicate, stale and already-handled notifications are settled by software
  before they reach a model: one model call where agent-managed handovers
  needed four. Krystal Unity runs its own development this way, with
  [69 agent sessions on one bus](case-studies/semio-live-bus-2026-11-10/README.md).
- **A stopping point.** Every run has a cost limit, a step limit and a repair
  limit, and ends with a receipt.

### What We Have Measured

- **Feature benchmark, 66 tasks.** @@MEASURED_BENCH@@
  [Case study and receipts](case-studies/feature-benchmark-2026-11-10/README.md).
- **Semio coordination.** Four coordination model calls became one, input
  tokens fell from 5,325 to 1,331 (75%), and both paths handled all four
  scenarios correctly.
  [Case study and receipts](case-studies/semio-coordination-2026-10-20/README.md).
- **A real coding repair in a 255-file snapshot.** A DeepSeek worker with
  frontier review cost $0.2709 against $0.3595 for the conventional frontier
  workflow, 24.6% lower, with all candidates passing the same 15 checks.
  [Case study and receipts](case-studies/krystalview-2026-10-20/README.md).
- **Compact context packets.** 21% fewer reported input tokens on a
  documentation assignment and 24.6% fewer on a source-review pilot, with the
  same review outcomes.
- **Event wake.** Waiting for a handover took 3 transport reads in place of 21.

[Every measurement, with its method and receipts](EVIDENCE.md).

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

Start with the [DeepSeek Codex worker](examples/deepseek-codex-worker/README.md),
then use the
[OpenAI-compatible critic harness](examples/openai-compatible-critic/README.md).
The worker launcher uses an isolated Codex profile and a reviewed assignment.
The critic makes one request by default, validates its structured verdict locally,
and cannot edit or authorize any action. Its optional bounded evidence-read mode
can retrieve selected generated source from the sealed packet. The examples do not automatically connect
worker output to critic input; the controller must inspect and redact the
review packet first.

### Review Generated Source

Use the [maintained critic quick-start](examples/openai-compatible-critic/README.md#review-generated-source)
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

The [fail-review-repair fixture](examples/fail-review-repair/README.md) proves a
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

The [capability-regression fixture](examples/capability-regression/README.md)
proves the v0.3 product-truth gate. It establishes an accepted baseline,
deliberately regresses an adaptive capability while task checks pass, blocks
completion, repairs within the declared limit, and proves the repaired
integrated artifact. Both lifecycle fixtures run offline.

## Let Software Run the Repetitive Checks

An AI reviewer should judge the evidence, not spend turn after turn launching
the same tests. The optional [capability audit runner](examples/capability-audit/README.md)
runs approved checks against frozen before-and-after versions, isolates each
execution, and prepares a compact evidence packet for independent review.

The collector makes no model calls. It retains failed checks and incomplete
evidence instead of converting them into a green result. Use it when a task
already needs a capability audit; ordinary Standard work stays lightweight.

The runner has been exercised on a real, asset-heavy game repository: 42 probe
executions including preflight and a bounded correction. See the
[validation note](examples/capability-audit/VALIDATION.md). Linux, Python, Git
and Bubblewrap are required.

## Read Next

- [Feature benchmark: run it yourself](bench/README.md)
- [Feature benchmark results and receipts](case-studies/feature-benchmark-2026-11-10/README.md)
- [Semio in daily use: 69 agent sessions on one bus](case-studies/semio-live-bus-2026-11-10/README.md)
- [Standard and Critical execution profiles](EXECUTION_PROFILES.md)
- [Compact Standard task record](examples/standard-task.md)
- [Solo-operator role example](examples/solo-operator.md)
- [Public demo and evidence verification](VERIFY.md)
- [Public coding challenge for your own agents](https://github.com/KrystalUnity/klp-public-challenge)
- [KLP Core protocol for Critical work](PROTOCOL.md)
- [Recovering missing capability proof](PROTOCOL.md#recovering-missing-capability-proof)
- [Instructions for AI agents and orchestrators](AI_AGENT_INTEGRATION.md)
- [Optional runtime profiles](RUNTIME_PROFILES.md)
- [Safety and limits](SAFETY_AND_LIMITS.md)
- [DeepSeek Codex worker example](examples/deepseek-codex-worker/README.md)
- [OpenAI-compatible critic example](examples/openai-compatible-critic/README.md)
- [Offline fail-review-repair fixture](examples/fail-review-repair/README.md)
- [Offline capability-regression fixture](examples/capability-regression/README.md)
- [Optional deterministic capability audit runner](examples/capability-audit/README.md)
- [Hermes Kanban adapter example](adapters/hermes-kanban.md)
- [Optional Semio agent-coordination adapter](adapters/semio.md)
- [Compact context packet guide](examples/semio-coordination/CONTEXT_PACKETS.md)
- [Measured results](EVIDENCE.md)

## Where KLP Fits

KLP is a portable way to bound multi-agent work, keep useful evidence and make
every acceptance traceable to a check that ran and a review of the exact
result. It works with the models, Git workflow and CI you already have.

**KLP checks how software changes earn acceptance; runtime controls govern what
that software can do after deployment.** The two layers complement each other.

KLP is inspired by public builder/critic systems such as the
[Gauntlet Loop](https://somethingbig.ai/gauntlet-loop). Its focus is what
happens after the demo, when a real project must stay understandable and
working across many changes.

## Project Status

Runner **0.4.0** with protocol profile **v0.3.3-draft**. Standard
(`klp-standard/v0.1`) now has a one-command runner, `klp run`, and a public
benchmark. Critical keeps `klp-core/v0.3` with its capability gate, sealed
critic harness and offline lifecycle fixtures.

## License

Krystal Loop Protocol uses split licensing:

- software, scripts, schemas, configuration examples, and tests are licensed
  under [Apache License 2.0](LICENSE-APACHE-2.0) (`Apache-2.0`);
- protocol and documentation text are licensed under
  [Creative Commons Attribution 4.0](LICENSE-CC-BY-4.0) (`CC-BY-4.0`).

See the [licensing map](LICENSE) for the file-level boundary.
