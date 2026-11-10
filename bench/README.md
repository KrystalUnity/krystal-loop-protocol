# KLP Feature Benchmark

Sixty-six real feature tasks in three open-source Python libraries, each graded
by tests the models never see. Run it yourself and compare a frontier model
working alone with a low-cost worker under KLP Standard.

Latest result: KLP Standard solved 57 of 66 for $0.073 a task; the frontier
model alone solved 56 for $0.173 a task. Both arms together cost $16.22 and
took 33 minutes. [Case study and receipts](../case-studies/feature-benchmark-2026-11-10/README.md).

## What is measured

| Arm | Who does the work | Who checks it |
| --- | --- | --- |
| Frontier model alone | `gpt-6.1-sol`, high reasoning | nobody |
| Low-cost worker alone | `deepseek-flash` | nobody |
| KLP Standard | the same `deepseek-flash` run | `gpt-6.1-sol` as independent critic, findings settled by executed probes, one bounded repair |

The low-cost worker alone and KLP Standard share one worker run. The benchmark
grades the worker's candidate before review and the final candidate after
review, so the difference between those two rows is exactly what review and
repair changed and what they cost.

Every arm gets the same task statement, the same sandbox, the same shell tool
and the same step limit. A task counts as solved when its hidden test files
pass on the final candidate.

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
python3 -m bench.features run --work ~/klp-bench --cap 25     # hard spend limit in USD
python3 -m bench.features report --work ~/klp-bench
```

Useful options:

- `--arms klp` runs only the KLP arm.
- `--limit 10` runs the first ten tasks; `--ids a,b` runs named tasks.
- `--jobs 8` sets how many tasks run at once.
- Re-running `run` resumes: finished tasks are skipped.

The run stops making model calls when the cap is reached. Spend is priced from
each provider's reported token usage with the rates in
[`klp/prices.json`](../klp/prices.json); edit that file if your prices differ.

## Use other models

Edit [`models.json`](models.json). Any OpenAI-compatible chat endpoint works
for the worker and the critic, including a local model. The worker and critic
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
