# Feature Benchmark: One More Task Solved at 42% of the Cost

A low-cost worker under KLP Standard solved 57 of 66 real feature tasks for
$0.073 a task. A frontier model working alone solved 56 for $0.173 a task. The
tasks are single features in Click, Jinja and dirty-equals, each graded by
tests the models never see. Run on 10 November 2026.

| | Tasks solved | Cost per task | Cost per solved task | All 66 tasks | Findings confirmed and fixed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Frontier model alone (`gpt-6.1-sol`, high reasoning) | 56 | $0.173 | $0.203 | $11.39 | not reviewed |
| Low-cost worker alone (`deepseek-flash`) | 56 | $0.024 | $0.028 | $1.59 | not reviewed |
| **KLP Standard** (that worker, `gpt-6.1-sol` critic, one bounded repair) | **57** | **$0.073** | **$0.085** | **$4.83** | **43** |

KLP Standard cost 58% less per task than the frontier model alone and solved
one more task. The whole benchmark, both arms, took 33 minutes at ten tasks in
parallel and cost $16.22 across 2,321 model calls.

## What independent review added

The low-cost worker alone and KLP Standard are the same worker runs. The
benchmark grades the worker's candidate before review and the final candidate
after review, so the difference between those two rows is the review itself.

- **64 findings confirmed by execution.** The critic reviewed all 66
  candidates. Each blocking finding came with a probe test, and the runner ran
  it against the candidate. 64 probes failed, which confirms the finding.
- **43 fixed and verified before handover.** 36 candidates went to their one
  bounded repair. Of the 44 findings sent to repair, 43 probes passed
  afterwards. Every repair kept the declared checks passing.
- **One hidden-test failure turned into a pass.** On `click-task2956-feature3`
  the critic confirmed that an option field was missing from the info
  dictionary and that a new parameter broke existing positional calls. The
  repair closed both, and the task's hidden tests then passed.
  [Receipt](receipts/pallets_click-task2956-feature3.md).
- **No repair broke a passing task.** All 56 candidates that passed their
  hidden tests before review still passed after it.
- **3 findings discarded by evidence.** The critic reported that constructing
  `IsURL()` would raise a `NameError`. The probe ran and passed, so the finding
  was dropped and no repair was spent on it.
  [Receipt](receipts/samuelcolvin_dirty_equals-task43-feature4.md).

The confirmed findings are the kind that pass a test suite and fail in use:

- a timeout that stopped the shell wrapper and left the editor process running;
- shell metacharacters in editor arguments reaching `cmd.exe` unescaped;
- process monitoring that tracked the shell wrapper's PID in place of the editor's;
- shell completion closing a context before the completion callback used it;
- a saved resource state held by reference, so a restore did not undo later
  registrations.

Each run ends with a receipt that lists what was confirmed, what was fixed and
what is still open. 48 runs finished `completed`. 18 finished
`budget_exhausted`: the second review confirmed a further finding after the one
permitted repair, and the receipt hands those to you with their failing probes.

## Where the money went

| KLP Standard, all 66 tasks | Calls | Cost | Share |
| --- | ---: | ---: | ---: |
| Worker (`deepseek-flash`) | 1,331 | $1.59 | 33% |
| Critic (`gpt-6.1-sol`) | 102 | $2.91 | 60% |
| Repair (`deepseek-flash`) | 252 | $0.32 | 7% |
| Total | 1,685 | $4.83 | 100% |

The low-cost model made 94% of the calls and read 42.8 million input tokens,
96.7% of them from cache. The frontier model was called 102 times, once per
review, on a compact packet with a median size of 14.5 KB: the task, the diff
with its enclosing functions, and the executed check output. The frontier model
working alone made 636 calls and read 8.0 million input tokens.

## Method

- **Tasks.** 66 single-feature tasks from the public
  [CooperBench](https://github.com/cooperbench/CooperBench) dataset at revision
  `63b9d44d`: 27 in Click, 30 in Jinja and 9 in dirty-equals, across seven base
  commits. Each has a written specification, a reference patch and a hidden
  test patch. Before any model ran, every task was validated: existing tests
  pass on the base commit, the hidden tests fail without the feature, and they
  pass with the reference patch.
- **Same conditions for every arm.** The same task statement, the same
  bubblewrap sandbox with no network, one shell tool, at most 40 worker steps
  and a $2 limit per task.
- **Frontier model alone.** `gpt-6.1-sol` through the Responses API at high
  reasoning effort.
- **KLP Standard.** `deepseek-flash` with thinking enabled as the worker, then
  the runner executes the declared check (the task's existing test files),
  `gpt-6.1-sol` reviews the exact candidate once, probes settle the findings,
  and confirmed findings get one repair of at most 20 steps followed by a
  second review.
- **Grading.** Each candidate's patch is applied to a pristine checkout, the
  hidden test files replace the candidate's versions, and the task's test files
  must pass. Models never see the hidden tests or their results.
- **Cost.** Calculated from provider-reported token usage at the rates in
  [`prices.json`](prices.json). DeepSeek is priced at its standard rate
  throughout. All 2,321 calls completed and are in the ledger.
- **Code.** Runner revision `9f33aa8`.

## Check it and run it

```bash
python3 case-studies/feature-benchmark-2026-11-10/verify.py
```

The checker reprices every call in [`ledger.jsonl`](ledger.jsonl), sums the
calls for each run in [`results.json`](results.json) and rebuilds the table in
[`report.json`](report.json). [`tasks.json`](tasks.json) lists every task with
its repository, commit and validation result, and [`models.json`](models.json)
holds the exact model settings.

To rerun it with your own keys or your own models, follow the
[benchmark guide](../../bench/README.md). The KLP arm alone costs about $5.
