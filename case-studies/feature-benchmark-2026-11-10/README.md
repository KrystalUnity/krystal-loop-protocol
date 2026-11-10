# Feature Benchmark: Frontier Solve Rate at a Thirteenth of the Heavy Model's Cost

Across two runs, a low-cost worker under KLP Standard solved 57 and 54 of 66
real feature tasks for $0.055 and $0.061 a task. OpenAI's heaviest model
working alone solved 56 for $0.721 a task, and its standard frontier model
solved 56 for $0.123. The tasks are single features in Click, Jinja and
dirty-equals, each graded by tests the models never see. Run on 10 November
2026: 462 runs, 6,165 model calls.

| | Tasks solved | Cost per task | Cost per solved task | All 66 tasks |
| --- | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`, high reasoning) | 56 | $0.721 | $0.849 | $47.57 |
| Frontier model alone (`gpt-6.1-sol`, high reasoning) | 56 | $0.123 | $0.146 | $8.15 |
| **KLP Standard, run 1** (`deepseek-flash` worker, `gpt-6.1-sol` critic, one repair round) | **57** | **$0.055** | **$0.064** | **$3.64** |
| **KLP Standard, run 2** (same models, two repair rounds) | **54** | **$0.061** | **$0.074** | **$4.00** |
| Low-cost worker alone, run 1 / run 2 (`deepseek-flash`) | 56 / 54 | $0.024 / $0.027 | $0.028 / $0.034 | $1.59 / $1.81 |

KLP Standard cost 92% less per task than the heavy model alone and 51% to 55%
less than the frontier model alone, at the same solve rate: every arm lands
between 54 and 57 of 66. The saving grows with the price of the model you would
otherwise run alone, because under KLP that model reads one review packet per
candidate and nothing else.

## What independent review added

Each KLP row and the low-cost worker row beside it are the same worker runs,
graded before and after review. The difference is the review itself.

| | Run 1, one repair round | Run 2, two repair rounds |
| --- | ---: | ---: |
| Findings confirmed by a failing probe | 64 | 78 |
| Findings fixed and verified before handover | 43 | 67 |
| Findings discarded because their probe passed | 3 | 2 |
| Runs ending `completed` | 48 | 56 |
| Runs ending with a confirmed finding still open | 18 | 10 |
| Hidden-test failures turned into passes | 1 | 0 |
| Passing candidates broken by a repair | 0 | 0 |

- **Findings are settled by execution.** Each blocking finding comes with a
  probe test, and the runner runs it against the candidate. A failing probe
  confirms the finding. A passing probe discards it: the critic reported that
  constructing `IsURL()` would raise a `NameError`, the probe passed, and no
  repair was spent.
  [Receipt](receipts/klp--samuelcolvin_dirty_equals-task43-feature4.md).
- **A second repair round closes more.** With one round, 67% of confirmed
  findings were fixed before handover; with two, 86%, for about a fifth of a
  cent more review and repair per task.
- **Review can rescue a failing task.** On `click-task2956-feature3` the critic
  confirmed that an option field was missing from the info dictionary and that
  a new parameter broke existing positional calls. The repair closed both, and
  the task's hidden tests then passed.
  [Receipt](receipts/klp--pallets_click-task2956-feature3.md).
- **No repair broke a passing task** in either run with the Sol critic.

The confirmed findings are the kind that pass a test suite and fail in use:

- a timeout that stopped the shell wrapper and left the editor process running;
- shell metacharacters in editor arguments reaching `cmd.exe` unescaped;
- process monitoring that tracked the shell wrapper's PID in place of the editor's;
- shell completion closing a context before the completion callback used it;
- a saved resource state held by reference, so a restore did not undo later
  registrations.

A run that ends with a finding still open hands it to you in the receipt with
its failing probe.

## Which critic

In run 2 three critics reviewed the identical 66 worker candidates: the same
files, the same snapshot and the same worker session, with two repair rounds.

| Critic | Tasks solved after review | Cost per task, worker included | Findings confirmed | Fixed | Runs with a finding still open | Passing tasks broken |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol` | 54 | $0.061 | 78 | 67 | 10 | 0 |
| `gpt-6-astra` (heavier, 5x the price) | 55 | $0.165 | 81 | 72 | 9 | 0 |
| `gpt-6.1-terra` (lighter, half the price) | 52 | $0.075 | 222 | 167 | 32 | 3 |

- **The standard frontier model is the right critic.** The heavier critic
  confirmed almost the same findings, rescued one more task and cost 2.7 times
  as much per task.
- **A lighter critic costs more, and costs quality.** It raised three times as
  many findings, drove 93 repairs against 51, left 32 runs with findings open
  and broke three candidates that had passed their hidden tests.

## Where the money went

| KLP Standard, all 66 tasks | Run 1 | Run 2 |
| --- | ---: | ---: |
| Worker (`deepseek-flash`) | $1.59 | $1.81 |
| Critic (`gpt-6.1-sol`) | $1.73 for 102 reviews | $1.74 for 117 reviews |
| Repair (`deepseek-flash`) | $0.32 | $0.46 |
| Total | $3.64 | $4.00 |

The low-cost model makes about 94% of the calls and reads over 96% of its
input from cache. The frontier model is called once per review on a compact
packet with a median size of about 15 KB: the task, the diff with its enclosing
functions, and the executed check output. In run 2 each review is a single
request sent without a cache write, which lowers the cost per review from
$0.017 to $0.015.

| Working alone, all 66 tasks | Calls | Input tokens | Cost |
| --- | ---: | ---: | ---: |
| `gpt-6-astra` | 660 | 8.8 million | $47.57 |
| `gpt-6.1-sol` | 636 | 8.0 million | $8.15 |

## The tasks every arm missed

Seven tasks were failed by both models working alone, by both worker runs and
by every KLP arm. Their hidden tests check behaviour the written specification
does not state, such as `IsCreditCard["Visa"]` subscript syntax or how a
three-element path tuple is handled. On the other 59 tasks, KLP Standard solved
57 in run 1 and 54 in run 2.

## Method

- **Tasks.** 66 single-feature tasks from the public
  [CooperBench](https://github.com/cooperbench/CooperBench) dataset at revision
  `63b9d44d`: 27 in Click, 30 in Jinja and 9 in dirty-equals, across seven base
  commits. Each has a written specification, a reference patch and a hidden
  test patch. Before any model ran, every task was validated: existing tests
  pass on the base commit, the hidden tests fail without the feature, and they
  pass with the reference patch.
- **Same conditions for every arm.** The same task statement, the same
  bubblewrap sandbox with no network and one shell tool.
- **Models alone.** `gpt-6-astra` and `gpt-6.1-sol` through the Responses API
  at high reasoning effort. The longest run took 17 calls.
- **KLP Standard.** `deepseek-flash` with thinking enabled as the worker. The
  runner executes the declared check (the task's existing test files), the
  critic reviews the exact candidate, probes settle the findings, and confirmed
  findings go to a bounded repair followed by another review. Run 1 allowed 40
  worker steps and one repair round. Run 2 allowed 100 worker steps and two
  repair rounds; its longest worker run took 70 steps.
- **Grading.** Each candidate's patch is applied to a pristine checkout, the
  hidden test files replace the candidate's versions, and the task's test files
  must pass. Models never see the hidden tests or their results.
- **Cost.** Calculated from provider-reported token usage at the published
  rates in [`prices.json`](prices.json), taken from the providers' pricing
  pages on the day. The runs fell in DeepSeek's peak-rate hours.
- **Code.** Run 1 and `gpt-6.1-sol` alone at runner revision `9f33aa8`; run 2,
  the critic arms and `gpt-6-astra` alone at `33e7ccd`.

To repeat run 2 with the standard critic:

```bash
python3 -m bench.features run --work ~/klp-bench --cap 15 --arms frontier-solo,worker,klp-sol
```

Add `astra-solo` (about $48), `klp-astra` or `klp-terra` to the arms for the
other rows. Run 1's settings are `--arms klp --max-steps 40 --repair-rounds 1`.

## Check it and run it

```bash
python3 case-studies/feature-benchmark-2026-11-10/verify.py
```

The checker reprices every call in [`ledger.jsonl`](ledger.jsonl), sums the
calls for each run in [`results.json`](results.json) and rebuilds the table in
[`report.json`](report.json). In those files run 1 is the arm `klp` and run 2
is `worker` plus `klp-sol`. [`tasks.json`](tasks.json) lists every task with
its repository, commit and validation result, and [`models.json`](models.json)
holds the model settings.

To rerun it with your own keys or your own models, follow the
[benchmark guide](../../bench/README.md). The KLP arm alone costs about $4.
