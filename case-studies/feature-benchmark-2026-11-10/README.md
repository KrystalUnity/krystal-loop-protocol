# Feature Benchmark: More Tasks Solved Than the Heavy Model, at a Sixteenth of Its Cost

A low-cost worker under KLP Standard solved 59 of 66 real feature tasks for
$0.046 a task. OpenAI's heaviest model working alone solved 56 for $0.721 a
task, and its standard frontier model solved 56 for $0.123. Across three KLP
runs the result was 57, 54 and 59 solved at $0.055, $0.061 and $0.046. The
tasks are single features in Click, Jinja and dirty-equals, each graded by
tests the models never see. Run on 10 November 2026: 990 runs, 9,696 model
calls.

| | Tasks solved | Cost per task | Cost per solved task | All 66 tasks |
| --- | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`, high reasoning) | 56 | $0.721 | $0.849 | $47.57 |
| Frontier model alone (`gpt-6.1-sol`, high reasoning) | 56 | $0.123 | $0.146 | $8.15 |
| **KLP Standard, run 3** (runner 0.5, `deepseek-flash` worker, `gpt-6.1-sol` critic) | **59** | **$0.046** | **$0.051** | **$3.02** |
| KLP Standard, run 2 (two repair rounds) | 54 | $0.061 | $0.074 | $4.00 |
| KLP Standard, run 1 (one repair round) | 57 | $0.055 | $0.064 | $3.64 |
| Low-cost worker alone, runs 1 / 2 / 3 (`deepseek-flash`) | 56 / 54 / 57 | $0.024 / $0.027 / $0.014 | $0.028 / $0.034 / $0.016 | $1.59 / $1.81 / $0.93 |

Run 3 cost 94% less per task than the heavy model alone and 63% less than the
frontier model alone, and solved three more tasks than either. It solved five
tasks the heavy model missed. Over the three runs KLP Standard cost 92% to 94%
less than the heavy model and 51% to 63% less than the frontier model.

Run 3 used runner 0.5 and ran in DeepSeek's off-peak hours, when the worker is
billed at half rate. Each call is priced at the rate in force when it ran.

## What runner 0.5 changed

Runs 1 and 2 showed where review was leaving tasks on the table. Runner 0.5
closes those gaps, and the same critic on the same 66 candidates shows the
effect:

| `gpt-6.1-sol` critic on the identical run 2 candidates | Earlier runner | Runner 0.5 |
| --- | ---: | ---: |
| Tasks solved after review | 54 | 56 |
| Cost per task, worker included | $0.061 | $0.060 |
| Findings confirmed by a failing probe | 78 | 86 |
| Fixed and verified before handover | 67 | 76 |
| Hidden-test failures turned into passes | 0 | 2 |
| Passing candidates broken by a repair | 0 | 0 |

- **Probes run under the project's own test rules.** Click treats warnings as
  errors. A timeout feature that leaves a child process unreaped shows up only
  as a warning, so under the earlier runner the candidate passed every probe
  and failed the hidden tests. With the project's rules applied to probes, the
  problem fails a probe, the repair fixes it, and the task passes.
  [Receipt](receipts/klp-3--pallets_click-task2068-feature2.md).
- **A confirmed finding stays open until its probe passes.** The repair is
  re-run against every open probe, and a finding the repair did not close is
  carried into the next round. The critic can withdraw a finding when the
  worker shows the task does not require it.
- **The critic checks conventions the task leaves open**, such as which
  exception type the surrounding code raises or where a new argument goes.

## What independent review added

Each KLP row and the worker row beside it are the same worker runs, graded
before and after review. The difference is the review itself.

| | Run 1 | Run 2 | Run 3 |
| --- | ---: | ---: | ---: |
| Findings confirmed by a failing probe | 64 | 78 | 77 |
| Findings fixed and verified before handover | 43 | 67 | 70 |
| Findings discarded because their probe passed | 3 | 2 | 3 |
| Runs ending `completed` | 48 | 56 | 58 |
| Runs ending with a confirmed finding still open | 18 | 10 | 8 |
| Hidden-test failures turned into passes | 1 | 0 | 2 |
| Passing candidates broken by a repair | 0 | 0 | 0 |

- **Findings are settled by execution.** Each blocking finding comes with a
  probe test, and the runner runs it against the candidate. A failing probe
  confirms the finding. A passing probe discards it: the critic reported that
  constructing `IsURL()` would raise a `NameError`, the probe passed, and no
  repair was spent.
  [Receipt](receipts/klp--samuelcolvin_dirty_equals-task43-feature4.md).
- **Repair rounds close what review finds.** One round fixed 67% of confirmed
  findings before handover, two rounds 86%, and runner 0.5 with two rounds 91%.
- **Review rescues failing tasks.** In run 3 the review turned two hidden-test
  failures into passes; in run 1, one.
  [Receipt](receipts/klp-3--pallets_click-task2800-feature2.md).
- **No repair broke a passing task** in any run with the Sol critic.

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

Critics reviewed the identical 66 run 2 worker candidates: the same files, the
same snapshot and the same worker session, with two repair rounds.

| Critic, runner 0.5 | Tasks solved after review | Metered cost per task, worker included | Findings confirmed | Hidden-test failures rescued | Passing tasks broken |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol` (API) | 56 | $0.060 | 86 | 2 | 0 |
| Gemini 4 Argon, on an Antigravity CLI subscription | 56 | $0.028 | 5 | 2 | 0 |
| `grok-4.7` (API) | 54 | $0.058 | 4 | 0 | 0 |

| Critic, earlier runner | Tasks solved after review | Cost per task, worker included | Findings confirmed | Fixed | Runs with a finding still open | Passing tasks broken |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol` | 54 | $0.061 | 78 | 67 | 10 | 0 |
| `gpt-6-astra` (heavier, 5x the price) | 55 | $0.165 | 81 | 72 | 9 | 0 |
| `gpt-6.1-terra` (lighter, half the price) | 52 | $0.075 | 222 | 167 | 32 | 3 |

- **The standard frontier model is the right metered critic.** The heavier
  critic rescued one more task for 2.7 times the cost. The lighter critic
  raised three times as many findings, drove 93 repairs against 51 and broke
  three candidates that had passed.
- **A subscription you already hold can do the review.** Gemini 4 Argon,
  reached through the Antigravity CLI, rescued the same two tasks as the Sol
  critic with five precise findings. The review adds no metered cost, so the
  whole loop costs $0.028 a task in metered spend: 96% below the heavy model
  alone, with the same solve count.
- **Critics differ in what they catch.** `grok-4.7` confirmed four findings and
  rescued nothing. Kimi K3.1 Pro, on its CLI subscription, reviewed 59 of the
  66 candidates before the subscription's usage window closed: 13 confirmed
  findings, one rescue and no passing task broken. Its runs are in the results
  as the arm `v2-kimi`.

## The acceptance file option

With `--acceptance` the critic also writes, on its first review, one test for
each behaviour the task statement spells out. The runner executes the file and
every failing test becomes a confirmed finding.

| `gpt-6.1-sol` critic, runner 0.5 | Without | With acceptance file |
| --- | ---: | ---: |
| Run 2 candidates: tasks solved | 56 | 57 |
| Run 2 candidates: cost per task | $0.060 | $0.074 |
| Run 3 candidates: tasks solved | 59 | 57 |
| Run 3 candidates: cost per task | $0.046 | $0.062 |

Of 132 acceptance files, 120 passed outright and 10 exposed a gap. The option
is there for work where a written specification must be covered line by line.
The default review reached the higher solve count at the lower cost.

## Where the money went

| KLP Standard, all 66 tasks | Run 1 | Run 2 | Run 3 |
| --- | ---: | ---: | ---: |
| Worker (`deepseek-flash`) | $1.59 | $1.81 | $0.93 |
| Critic (`gpt-6.1-sol`) | $1.73 for 102 reviews | $1.74 for 117 reviews | $1.85 for 119 reviews |
| Repair (`deepseek-flash`) | $0.32 | $0.46 | $0.25 |
| Total | $3.64 | $4.00 | $3.02 |

The low-cost model makes about 94% of the calls and reads over 96% of its
input from cache. The frontier model is called once per review on a compact
packet of about 15 KB: the task, the diff with its enclosing functions, the
executed check output and the project's test rules. A review costs one and a
half cents.

| Working alone, all 66 tasks | Calls | Input tokens | Cost |
| --- | ---: | ---: | ---: |
| `gpt-6-astra` | 660 | 8.8 million | $47.57 |
| `gpt-6.1-sol` | 636 | 8.0 million | $8.15 |

## The tasks every arm missed

Five tasks were failed by both models working alone, by all three worker runs
and by every KLP arm. Their hidden tests check behaviour the written
specification does not state. On the other 61 tasks, KLP Standard run 3 solved
59.

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
  worker steps and one repair round. Runs 2 and 3 allowed 100 worker steps and
  two repair rounds; the longest worker run took 70 steps.
- **Critic comparisons.** Every critic arm starts from the same recorded
  worker candidates, so the arms differ only in the review.
- **Subscription critics.** Gemini 4 Argon and Kimi K3.1 Pro were reached
  through their vendors' agent CLIs in read-only mode, in an empty directory.
  Their calls are recorded as unmetered.
- **Grading.** Each candidate's patch is applied to a pristine checkout, the
  hidden test files replace the candidate's versions, and the task's test files
  must pass. Models never see the hidden tests or their results.
- **Cost.** Calculated from provider-reported token usage at the published
  rates in [`prices.json`](prices.json), taken from the providers' pricing
  pages on the day. Runs 1 and 2 fell in DeepSeek's peak-rate hours and run 3
  in its off-peak hours; each call carries the tier it was billed at.
- **Repeated runs.** Three runs that a malformed critic reply stopped were
  repeated, and so were 13 `grok-4.7` runs whose probe file an earlier runner
  build could not locate. The Kimi arm's seven runs stopped by the usage
  window are reported as they ended.
- **Code.** Run 1 and `gpt-6.1-sol` alone at runner revision `9f33aa8`; run 2,
  the earlier critic arms and `gpt-6-astra` alone at `33e7ccd`; run 3 and the
  runner 0.5 arms at `f146aef` to `df2e27d`.

To repeat run 3:

```bash
python3 -m bench.features run --work ~/klp-bench --cap 15 --arms frontier-solo,worker-3,klp-3
```

Add `astra-solo` (about $48) for the heavy model, `v2-sol`, `v2-grok` or
`v2-argon` for the critic comparison, and `klp-3a` for the acceptance file.

## Check it and run it

```bash
python3 case-studies/feature-benchmark-2026-11-10/verify.py
```

The checker reprices every call in [`ledger.jsonl`](ledger.jsonl), sums the
calls for each run in [`results.json`](results.json) and rebuilds the table in
[`report.json`](report.json). In those files run 1 is the arm `klp`, run 2 is
`worker` plus `klp-sol`, and run 3 is `worker-3` plus `klp-3`.
[`tasks.json`](tasks.json) lists every task with its repository, commit and
validation result, and [`models.json`](models.json) holds the model settings.

To rerun it with your own keys or your own models, follow the
[benchmark guide](../../bench/README.md). The KLP arm alone costs about $3.
