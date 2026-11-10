# Documentation Map

## Start

| Page | What it gives you |
| --- | --- |
| [README](../README.md) | Results, the loop in six steps, and the one-command start |
| [How KLP works](how-it-works.md) | The loop in detail: findings, probes, states, the receipt, Semio |
| [Configuration](configuration.md) | Models, limits, sandbox, a critic on a subscription, `klp.json`, the command line |
| [For AI agents](../AGENTS.md) | Commands, expected outputs, citable facts and a summary for an operator |

## Evidence

| Page | What it gives you |
| --- | --- |
| [Benchmarks](../BENCHMARKS.md) | Both public benchmarks: results, how to check them offline and how to rerun them |
| [Measured results](../EVIDENCE.md) | Every measurement, with its method and receipts |
| [Verify it yourself](../VERIFY.md) | What each offline check and fixture proves |
| [evidence.json](../evidence.json) | The same facts for a program to read, with the commands that reproduce them |
| [Benchmark harness guide](../bench/README.md) | Arms, options and outputs of `bench.features` and `bench.pairs` |

Case studies, each with receipts and an offline checker:

- [Feature benchmark, 66 tasks](../case-studies/feature-benchmark-2026-11-10/README.md)
- [Paired features and Semio, 30 pairs](../case-studies/paired-features-2026-11-10/README.md)
- [SWE-bench Pro task in Ansible](../case-studies/ansible-workers-2026-10-27/README.md)
- [Semio coordination: four model calls became one](../case-studies/semio-coordination-2026-10-20/README.md)
- [Semio in daily use: 69 agent sessions on one bus](../case-studies/semio-live-bus-2026-11-10/README.md)
- [A real repair in a 255-file snapshot](../case-studies/krystalview-2026-10-20/README.md)

## Protocol

| Page | What it gives you |
| --- | --- |
| [Execution profiles](../EXECUTION_PROFILES.md) | Choosing Standard or Critical, and the routine release gate |
| [KLP Core protocol](../PROTOCOL.md) | The full Critical-path protocol with its capability gate |
| [Agent integration](../AI_AGENT_INTEGRATION.md) | Roles, context packets and handovers when you orchestrate the loop yourself |
| [Runtime profiles](../RUNTIME_PROFILES.md) | Optional role and runtime arrangements |
| [Safety and limits](../SAFETY_AND_LIMITS.md) | What the runner enforces and what stays with you |

## Wiring it into what you already run

| Page | What it gives you |
| --- | --- |
| [Your own agents](your-own-agents.md) | A starting prompt, worker and critic examples, offline fixtures |
| [Standard task record](../examples/standard-task.md) | The loop as one Markdown record, without the runner |
| [Solo operator](../examples/solo-operator.md) | The role setup for one person |
| [Semio adapter](../adapters/semio.md) | Typed coordination messages between agents |
| [Compact context packets](../examples/semio-coordination/CONTEXT_PACKETS.md) | Giving each agent only the material for its assignment |
| [Hermes Kanban adapter](../adapters/hermes-kanban.md) | Mapping KLP roles onto a Kanban runtime |
| [DeepSeek Codex worker](../examples/deepseek-codex-worker/README.md) | A low-cost worker launched under an isolated profile |
| [OpenAI-compatible critic](../examples/openai-compatible-critic/README.md) | A sealed, read-only critic harness for Critical work |
| [Capability-regression fixture](../examples/capability-regression/README.md) | The capability gate catching a regression that ordinary tests miss |
| [Fail-review-repair fixture](../examples/fail-review-repair/README.md) | A full bounded lifecycle offline |
| [Capability audit runner](../examples/capability-audit/README.md) | Software running repeated checks against frozen versions |

## Code

| Path | What it is |
| --- | --- |
| [`klp/`](../klp) | The Standard runner: worker loop, review, sandbox, snapshots, ledger, CLI |
| [`bench/`](../bench) | The two benchmark harnesses and the one-command verifier |
| [`tests/`](../tests) | Offline tests for the runner, the harnesses and the published facts |
| [`assets/make_charts.py`](../assets/make_charts.py) | Draws the README charts from the published reports |
| [`design-notes/`](design-notes) | Design notes from earlier protocol versions |
