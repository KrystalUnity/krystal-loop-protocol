# Benchmark Harness Guide

Two harnesses and a verifier, standard library only. Results, costs and the
quick reproduction path are in [BENCHMARKS.md](../BENCHMARKS.md); this page is
the manual.

| Command | What it does |
| --- | --- |
| `python3 -m bench.verify` | Recomputes every published figure from the receipts. Offline. |
| `python3 -m bench.features` | The 66-task feature benchmark. |
| `python3 -m bench.pairs` | The paired-features benchmark with Semio. |

Requirements for the two harnesses: Linux, Python 3.11+, Git,
[uv](https://docs.astral.sh/uv/) and bubblewrap (`apt install bubblewrap`). No
Docker and no virtual machine.

## Feature benchmark: `bench.features`

```bash
python3 -m bench.features prepare --work ~/klp-bench          # about 2 minutes, no model calls
python3 -m bench.features run --work ~/klp-bench --cap 15     # hard spend limit in USD
python3 -m bench.features report --work ~/klp-bench
```

### Arms

| Arm (`--arms`) | Who does the work | Who checks it |
| --- | --- | --- |
| `frontier-solo` | `gpt-6.1-sol`, high reasoning | nobody |
| `astra-solo` | `gpt-6-astra`, high reasoning | nobody |
| `worker-3` | `deepseek-flash` | nobody |
| `klp-3` | the `worker-3` arm's exact candidate | `gpt-6.1-sol` as independent critic, findings settled by executed probes, bounded repair |
| `klp-3a` | the same candidate | `klp-3` plus an acceptance test file written from the task statement |
| `worker` | a separate set of `deepseek-flash` candidates | nobody |
| `v2-sol`, `v2-grok`, `v2-argon`, `v2-kimi`, `v2-qwen` | the `worker` arm's exact candidate | the same loop with `gpt-6.1-sol`, `grok-4.7`, or Gemini 4 Argon, Kimi K3.1 Pro or Qwen 3.8 Max through their agent CLIs |
| `v2a-sol` | the `worker` arm's candidate | `v2-sol` plus the acceptance file |
| `klp-sol`, `klp-astra`, `klp-terra`, `klp` | as published | the earlier runner's arms, kept so the published packs can be repeated |

A review arm starts from another arm's candidates: the same files, the same
snapshot and the same worker session. Critics are therefore compared on
identical work, and the difference between a worker arm and its review arm is
exactly what review and repair changed and what they cost.

### Presets

`--preset` names a set of arms that repeats a published comparison.

| `--preset` | Arms |
| --- | --- |
| `headline` (the default) | `frontier-solo,worker-3,klp-3` |
| `heavy` | `astra-solo` |
| `critics` | `worker,v2-sol,v2-grok,v2-argon,v2-kimi,v2-qwen` |
| `acceptance` | `worker-3,klp-3,klp-3a` |

### Options

- `--arms a,b` runs named arms; `--preset` picks a set.
- `--cap` is the hard spend limit for this invocation. The run stops making
  model calls when it is reached.
- `--jobs 6` sets how many tasks run at once.
- `--limit 10` runs the first ten tasks; `--ids a,b` runs named tasks.
- `--max-steps`, `--repair-rounds` and `--task-cap` set the worker step limit,
  the repair rounds and the cost limit per task.
- Running `run` again resumes: finished tasks are skipped.
- `export --out DIR` writes an evidence pack: results, ledger, report, task
  list, models and prices.

### How a task is graded

`prepare` validates every task before any model runs: the existing tests pass
on the base commit, the hidden tests fail without the feature, and the hidden
tests pass with the reference patch. After a run, each candidate's patch is
applied to a pristine checkout, the hidden test files replace the candidate's
versions, and the task's test files must pass. Models never see the hidden
tests or their results.

### Grade a tool of your own

```bash
python3 -m bench.features tasks --work ~/klp-bench --out ~/my-run
python3 -m bench.features grade --work ~/klp-bench --patches ~/my-run --name my-setup --usd 4.10
```

`tasks` writes a clean checkout and `TASK.md` for each task. `grade` collects
what changed in each `<task-id>/repo`, or reads `<task-id>.patch`, and grades it
as above. Results go to `external/<name>/results.json`; a task with no patch is
unsolved. `--ids` limits either command to named tasks.
[Guide](../BENCHMARKS.md#grade-your-own-setup).

## Paired features: `bench.pairs`

```bash
python3 -m bench.pairs select --work ~/klp-bench --pairs 30
python3 -m bench.pairs run --work ~/klp-bench --arms merge,chat,semio,solo --cap 16
python3 -m bench.pairs report --work ~/klp-bench
```

It needs the `worker-3` and `klp-3` arms finished in the same `--work` folder.
`select` draws pairs, with a fixed `--seed`, from the dataset's conflicting
pairs whose two features both pass their hidden tests in `klp-3`.

| Arm | What happens |
| --- | --- |
| `merge` | git merges the two finished patches. No model. |
| `chat` | Both workers are woken, each can read the other's patch, and they agree in free-text messages who integrates. |
| `semio` | Each finished feature is a typed handover through the [Semio adapter](../examples/semio-coordination/README.md). Software merges and tests; when it cannot, it wakes one worker with the peer's exact artifact. |
| `solo` | `gpt-6.1-sol` builds both features alone from scratch. |

In the chat and Semio arms the runner executes both features' existing tests
on the integrated tree and allows one bounded repair. A pair passes when the
final tree passes both features' hidden tests, graded separately.

## Models and prices

[`models.json`](models.json) holds every model route the arms use. Any
OpenAI-compatible chat endpoint works for the worker and the critic, including
a local model. A critic can also be an agent CLI on a subscription
(`"api": "command"`); those arms need the CLI installed and signed in, and
`v2-grok` needs `XAI_API_KEY`. The worker and critic must be different model
families.

Spend is priced from each provider's reported token usage with the rates in
[`klp/prices.json`](../klp/prices.json). Add your model there so its calls are
priced.

## Output

```text
~/klp-bench/
  tasks.json                     validated task list
  ledger.jsonl                   one line per model call: role, tokens, price tier, cost, seconds
  runs/<arm>/<task>/receipt.md   what happened, in plain English
  runs/<arm>/<task>/receipt.json candidates, checks, reviews, findings, repairs, effort
  runs/<arm>/<task>/result.json  hidden-test grade for each candidate
  report.json                    the comparison table
  pairs.json                     the selected pairs
  pair-runs/<arm>/<pair>/result.json
  pairs-ledger.jsonl, pairs-report.json
```

Model-written code and test commands run inside a bubblewrap sandbox with no
network and no access to your home directory, environment or keys.
