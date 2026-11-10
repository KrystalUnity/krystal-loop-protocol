# KLP Feature Benchmark

Sixty-six real feature tasks in three open-source Python libraries, each graded
by tests the models never see. Run it yourself and compare a frontier model
working alone with a low-cost worker under KLP Standard.

Latest result: KLP Standard solved 59 of 66 for $0.046 a task, and 57 and 54
in two earlier runs. The heavy model alone solved 56 for $0.721 and the
frontier model alone solved 56 for $0.123.
[Case study and receipts](../case-studies/feature-benchmark-2026-11-10/README.md).

## What is measured

| Arm (`--arms`) | Who does the work | Who checks it |
| --- | --- | --- |
| `frontier-solo` | `gpt-6.1-sol`, high reasoning | nobody |
| `astra-solo` | `gpt-6-astra`, high reasoning | nobody |
| `worker` | `deepseek-flash` | nobody |
| `v2-sol` | the `worker` arm's exact candidate | `gpt-6.1-sol` as independent critic, findings settled by executed probes, bounded repair |
| `v2-grok`, `v2-argon`, `v2-kimi`, `v2-qwen` | the same candidate | the same loop with `grok-4.7`, or with Gemini 4 Argon, Kimi K3.1 Pro or Qwen 3.8 Max through their agent CLIs on a subscription |
| `v2a-sol` | the same candidate | `v2-sol` plus an acceptance test file written from the task statement |
| `worker-3`, `klp-3`, `klp-3a` | a second set of `deepseek-flash` candidates | `gpt-6.1-sol` critic, without and with the acceptance file |
| `klp-sol`, `klp-terra`, `klp-astra` | the `worker` arm's candidate | the published comparison of three OpenAI critics, made with the earlier runner |
| `klp` | `deepseek-flash`, then review in one pass | `gpt-6.1-sol` critic; the worker's candidate is also graded before review |

The review arms start from the `worker` arm's candidates: the same files, the
same snapshot and the same worker session. Different critics are therefore
compared on identical work, and the difference between `worker` and a review
arm is exactly what review and repair changed and what they cost.

Every arm gets the same task statement, the same sandbox and the same shell
tool. A task counts as solved when its hidden test files pass on the final
candidate.

## The tasks

The tasks come from the public [CooperBench](https://github.com/cooperbench/CooperBench)
dataset, pinned to revision `63b9d44d`. Each one is a single feature for
[Click](https://github.com/pallets/click), [Jinja](https://github.com/pallets/jinja)
or [dirty-equals](https://github.com/samuelcolvin/dirty-equals) at a fixed
commit: a written specification, a reference patch and a hidden test patch.
Here each feature is implemented on its own by one worker.

`prepare` validates every task before any model runs: the existing tests pass
on the base commit, the hidden tests fail without the feature, and the hidden
tests pass with the reference patch. All 66 validate.

## Run it

Requirements: Linux, Python 3.11+, Git, [uv](https://docs.astral.sh/uv/) and
bubblewrap (`apt install bubblewrap`). No Docker and no virtual machine.

```bash
git clone https://github.com/KrystalUnity/krystal-loop-protocol.git
cd krystal-loop-protocol
export DEEPSEEK_API_KEY=...  OPENAI_API_KEY=...

python3 -m bench.features prepare --work ~/klp-bench          # about 2 minutes, no model calls
python3 -m bench.features run --work ~/klp-bench --cap 15     # hard spend limit in USD
python3 -m bench.features report --work ~/klp-bench
```

Useful options:

- `--arms worker,v2-sol` runs only the KLP arm (about $3 off-peak, $4 at DeepSeek's peak rate); the default adds `frontier-solo`.
- `--arms astra-solo` adds the heavy model alone (about $48).
- `--max-steps` and `--repair-rounds` set the worker and repair limits.
- `--limit 10` runs the first ten tasks; `--ids a,b` runs named tasks.
- `--jobs 8` sets how many tasks run at once.
- Re-running `run` resumes: finished tasks are skipped.

The run stops making model calls when the cap is reached. Spend is priced from
each provider's reported token usage with the rates in
[`klp/prices.json`](../klp/prices.json); edit that file if your prices differ.

## Use other models

Edit [`models.json`](models.json). Any OpenAI-compatible chat endpoint works
for the worker and the critic, including a local model. A critic can also be
an agent CLI on a subscription (`"api": "command"`); those arms need the CLI
installed and signed in, and `v2-grok` needs `XAI_API_KEY`. The worker and critic
must be different model families; the runner refuses a same-family critic.

## What you get

```text
~/klp-bench/
  tasks.json                     validated task list
  ledger.jsonl                   one line per model call: role, tokens, cost, seconds
  runs/<arm>/<task>/receipt.md   what happened, in plain English
  runs/<arm>/<task>/receipt.json candidates, checks, reviews, findings, repairs, effort
  runs/<arm>/<task>/result.json  hidden-test grade for each candidate
  report.json                    the comparison table
```

Model-written code and test commands run inside a bubblewrap sandbox with no
network and no access to your home directory, environment or keys.
