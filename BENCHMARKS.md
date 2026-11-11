# Benchmarks

Two public benchmarks you can check offline in a minute and rerun with your
own keys. Both use real open-source code, tests the models never see, and a
ledger of every model call.

| Benchmark | What it measures | Result |
| --- | --- | --- |
| [Feature benchmark](#feature-benchmark-66-tasks) | A low-cost worker under KLP Standard against frontier models working alone | **59 of 66 solved at $0.046 a task**; heavy model alone 56 at $0.721 |
| [Paired features](#paired-features-30-conflicting-pairs) | Two KLP workers joined by Semio against a frontier model alone, and Semio against agent chat | **28 of 30 pairs at $0.103**; frontier alone 22 at $0.196; 43% fewer model calls than chat |

## Check every number offline

No API keys, no network after the clone, standard library only:

```bash
git clone https://github.com/KrystalUnity/krystal-loop-protocol.git
cd krystal-loop-protocol
python3 -m bench.verify
```

```text
ok    Feature benchmark, 66 tasks
ok    Paired features and Semio, 30 pairs
ok    Semio coordination study
ok    SWE-bench Pro Ansible task
ok    KrystalView repair

Every published figure recomputes from the receipts.
```

Each checker reprices every recorded model call from its token usage, sums
the calls of each run, and rebuilds the published table from the per-run
results. `python3 -m bench.verify --tests` also runs the offline test suites
for the runner and both harnesses.

## Feature benchmark: 66 tasks

Sixty-six single-feature tasks in [Click](https://github.com/pallets/click),
[Jinja](https://github.com/pallets/jinja) and
[dirty-equals](https://github.com/samuelcolvin/dirty-equals). Each has a
written specification and a hidden test patch. Every arm gets the same task
statement, the same sandbox with no network, and one shell tool.

| | Tasks solved | Cost per task | Cost per solved task |
| --- | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`, high reasoning) | 56 | $0.721 | $0.849 |
| Frontier model alone (`gpt-6.1-sol`, high reasoning) | 56 | $0.123 | $0.146 |
| **KLP Standard, run 3** (`deepseek-flash` worker, `gpt-6.1-sol` critic) | **59** | **$0.046** | **$0.051** |
| KLP Standard, run 2 | 54 | $0.061 | $0.074 |
| KLP Standard, run 1 | 57 | $0.055 | $0.064 |
| Low-cost worker alone, runs 1 / 2 / 3 | 56 / 54 / 57 | $0.024 / $0.027 / $0.014 | |

Critics compared on identical worker output:

| Critic | Tasks solved after review | Metered cost per task | Findings confirmed | Passing tasks broken |
| --- | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol` (API) | 56 | $0.060 | 86 | 0 |
| Gemini 4 Argon (Antigravity CLI subscription) | 56 | $0.028 | 5 | 0 |
| Kimi K3.1 Pro (Kimi CLI subscription) | 55 | $0.028 | 16 | 0 |
| `grok-4.7` (API) | 54 | $0.058 | 4 | 0 |
| Qwen 3.8 Max (Qwen CLI subscription), 63 of 66 reviewed | 54 | $0.028 | 3 | 0 |

[Full results, method and receipts](case-studies/feature-benchmark-2026-11-10/README.md),
including a receipt for each of the 66 runs of run 3.

### Rerun it

Requirements: Linux, Python 3.11+, Git, [uv](https://docs.astral.sh/uv/) and
bubblewrap (`apt install bubblewrap`). No Docker and no virtual machine.

```bash
export DEEPSEEK_API_KEY=...  OPENAI_API_KEY=...

python3 -m bench.features prepare --work ~/klp-bench                     # about 2 minutes, no model calls
python3 -m bench.features run --work ~/klp-bench --preset headline --cap 15
python3 -m bench.features report --work ~/klp-bench
```

`prepare` fetches the dataset at its pinned revision, builds one environment
per base commit and validates all 66 tasks: the existing tests pass on the
base commit, the hidden tests fail without the feature, and they pass with the
reference patch. `run` stops making model calls at the cap, and running it
again resumes where it stopped.

| `--preset` | Arms it runs | What it repeats | Our cost |
| --- | --- | --- | ---: |
| `headline` (the default) | `frontier-solo`, `worker-3`, `klp-3` | Frontier model alone against KLP Standard | $8.15 + $3.02 |
| `heavy` | `astra-solo` | The heavy model alone | $47.57 |
| `critics` | `worker`, `v2-sol`, `v2-grok`, `v2-argon`, `v2-kimi`, `v2-qwen` | Five critics on identical worker output | $1.81 + $2.12 + $2.05, subscriptions unmetered |
| `acceptance` | `worker-3`, `klp-3`, `klp-3a` | The acceptance-file option | $3.02 + $3.16 |

To run the KLP arm alone, pass `--arms worker-3,klp-3`: about $3 in
DeepSeek's off-peak hours and $4 at its peak rate, in roughly 40 minutes at
`--jobs 6`. The `critics` preset needs `XAI_API_KEY` for `grok-4.7` and the
Antigravity, Kimi and Qwen CLIs installed and signed in; leave an arm out of
`--arms` to skip it.

### What to expect when you rerun

- **Solve counts move by a few tasks between runs.** Our three KLP runs solved
  57, 54 and 59; the worker alone 56, 54 and 57. Five tasks were failed by
  every arm.
- **Cost depends on the hour.** DeepSeek bills half rate outside 01:00 to 04:00
  and 06:00 to 10:00 UTC on weekdays. The ledger prices each call at the rate
  in force when it ran and records the tier.
- **Prices are in [`klp/prices.json`](klp/prices.json),** taken from the
  providers' pricing pages on 10 November 2026. Edit the file if yours differ.

### Grade your own setup

Run any coding tool on the same 66 tasks and grade it with the same hidden
tests: Claude Code, Cursor, Codex, Aider or your own agent. `prepare` needs no
API keys.

```bash
python3 -m bench.features prepare --work ~/klp-bench
python3 -m bench.features tasks --work ~/klp-bench --out ~/my-run
# for each folder in ~/my-run: give your tool TASK.md and let it work in repo/
python3 -m bench.features grade --work ~/klp-bench --patches ~/my-run --name my-setup --usd 4.10
```

`tasks` writes one folder per task: `repo/`, a clean checkout at the task's
commit, and `TASK.md`, the statement exactly as our arms receive it. `grade`
takes everything your tool changed in `repo/` (commits, edits and new files),
or a `<task-id>.patch` file in the same folder, applies it to a pristine
checkout, swaps in the hidden tests and runs them in the sandbox with no
network. A task with no patch counts as unsolved. `--usd` records what the
whole run cost you, as self-reported.

```text
my-setup: 41 of 66 tasks solved, 64 patches graded, $0.062 a task (self-reported) -> ~/klp-bench/external/my-setup/results.json
```

For a like-for-like run, give your tool what ours had: the task statement, the
checkout and a shell, with no network and no sight of the dataset folder. Each
`repo/` needs its own environment to run the existing tests
(`pip install -e ".[test]"` on Python 3.11).
To compare with the table above, post your solve count, your cost per task and
your `results.json`.

## Paired features: 30 conflicting pairs

Pairs of features in the same three libraries whose reference patches conflict
when merged, taken from the dataset's own conflict report. A pair passes when
one tree passes both features' hidden tests.

| | Pairs passing | Cost per pair | Model calls to integrate | Worker sessions woken |
| --- | ---: | ---: | ---: | ---: |
| Frontier model alone builds both features (`gpt-6.1-sol`) | 22 | $0.196 | | |
| **Two KLP workers, joined by Semio** | **28** | **$0.103** | **333** | **28** |
| Two KLP workers, coordinating by chat | 28 | $0.115 | 581 | 60 |
| Plain git merge of the two finished features | 2 | | 0 | 0 |

The chat and Semio rows start from the same two finished features, the same
workspaces and the same worker sessions, so they differ only in how the
integration is coordinated.

[Full results, method and receipts](case-studies/paired-features-2026-11-10/README.md).

### Rerun it

The pairs are drawn from features your own run has already built, so finish
the `worker-3` and `klp-3` arms above first:

```bash
python3 -m bench.pairs select --work ~/klp-bench --pairs 30
python3 -m bench.pairs run --work ~/klp-bench --arms merge,chat,semio,solo --cap 16
python3 -m bench.pairs report --work ~/klp-bench
```

`select` draws with a fixed seed from the conflicting pairs whose two features
both pass their hidden tests in your `klp-3` run, spread across the base
commits. The chat and Semio arms together cost under $1; the frontier arm cost
us $5.87. The four arms took 22 minutes at `--jobs 8`.

## Use your own models

Edit [`bench/models.json`](bench/models.json). Any OpenAI-compatible chat
endpoint works for the worker and the critic, including a local model. A
critic can also be an agent CLI on a subscription (`"api": "command"`). The
worker and critic must be different model families; the runner refuses a
same-family critic. Add your model's rates to
[`klp/prices.json`](klp/prices.json) so its calls are priced.

## What is pinned

| | |
| --- | --- |
| Dataset | [CooperBench](https://github.com/cooperbench/CooperBench) at revision `63b9d44d9f39a02fccf5bf0052db48a917a011fd` |
| Tasks | 27 in Click, 30 in Jinja, 9 in dirty-equals, across seven base commits; listed with commits in each pack's `tasks.json` |
| Pairs | 30 of 162 eligible, seed `20261110`; listed in `pairs.json` |
| Models and settings | [`bench/models.json`](bench/models.json), copied into each pack |
| Prices | [`klp/prices.json`](klp/prices.json), copied into each pack |
| Prompts | In the code: [`klp/worker.py`](klp/worker.py), [`klp/review.py`](klp/review.py), [`bench/pairs.py`](bench/pairs.py) |
| Limits | 100 worker steps, 40 repair steps, two repair rounds, $2 per task |
| Runner revisions | Named in each case study's method section |

## What you get from a run

```text
~/klp-bench/
  tasks.json                     validated task list
  ledger.jsonl                   one line per model call: role, tokens, price tier, cost, seconds
  runs/<arm>/<task>/receipt.md   what happened, in plain English
  runs/<arm>/<task>/receipt.json candidates, checks, reviews, findings, repairs, effort
  runs/<arm>/<task>/result.json  hidden-test grade for each candidate
  report.json                    the comparison table
  pairs.json, pair-runs/, pairs-ledger.jsonl, pairs-report.json   the paired benchmark
```

Model-written code and test commands run inside a bubblewrap sandbox with no
network and no access to your home directory, environment or keys.

## Share your result

Send the commit, your `report.json`, the models and prices you used, and the
date and hour of the run. Results with other workers and critics are welcome,
including ones where the loop did worse.

The harness options are in the [benchmark guide](bench/README.md).
