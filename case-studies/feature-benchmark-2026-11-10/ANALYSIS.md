# A Second Look at the 66-Task Benchmark

KLP Standard's best run solved 59 of 66 tasks. OpenAI's heaviest model working
alone solved 56, at sixteen times the cost per task while KLP's DeepSeek calls
ran off-peak, and about eleven times at DeepSeek's peak price. Readers pushed on that
result with four questions: is the gap more than chance, does it hold on bigger
tasks, how many tokens does it burn, and are the critic's findings real? We
added a fifth: does the receipt tell you when the work is wrong? This page
answers each one from the published receipts, with no new model calls.
Every table recomputes offline:

```bash
python3 case-studies/feature-benchmark-2026-11-10/verify.py
```

## In short

- **No detectable difference in pass rate.** Run 3 solved 59 tasks and the
  heavy model 56. They disagree on 7 tasks, 5 to 2, which is within chance
  (p = 0.45). The difference is +4.5 points, and its 95% interval runs from
  −4.3 to +13.8: 66 tasks cannot tell gaps of this size apart. Across three
  runs the loop solved 54 to 59, and its worker alone 54 to 57.
- **The cost is the result, and most of the saving is the worker model.** Run 3
  cost $0.046 a task, against $0.721 for the heavy model and $0.123 for the
  frontier model. Its DeepSeek calls ran in off-peak hours at half rate. At
  DeepSeek's standard rate, which runs 1 and 2 paid, the three runs cost 11 to
  13 times less than the heavy model and about half as much as the frontier
  model. The DeepSeek worker alone was also within chance of the heavy model,
  at a twenty-sixth to a thirtieth of its cost. With review and repair, KLP
  Standard costs 2.2 to 2.3 times the worker alone, and review added 1, 0 and
  2 solved tasks without breaking one, which is also within chance.
- **No size effect shows up, and these tasks are small.** No two arms differ
  by more than chance in any size, file-count or repository group. Every arm
  solved a little less of the largest third, where three of the five tasks no
  arm solved sit. No reference solution here is longer than 232 changed lines
  or touches more than two files.
- **More tokens, cheaper tokens.** The loop uses five to seven and a half
  times as many tokens per solved task as the frontier model alone. Nearly all
  of them are the low-cost model's, and 97% of its input comes from cache.
  Frontier-model tokens per solved task fall from 150 thousand to 11 thousand.
- **The probes reproduce; that does not make every finding right.** Every
  confirmed finding we could rerun, 637 of 764, failed again on its candidate
  with the same exit code. A failing probe shows the candidate fails that test,
  not that the test is right: some confirmed findings fail on a mistake in the
  probe, and at least one asks for what the task statement rules out. On the
  dataset's reference solution, about four in ten of the Sol critic's
  confirmed findings pass, 57% fail there too and 5% cannot run. No repair
  under a Sol critic broke a passing task.
- **The receipt does not yet tell you when the work is wrong.** In run 3, 6
  of the 7 tasks that failed the hidden tests ended with a clean receipt, and
  7 of the 8 receipts that ended with something unresolved had passed. When
  a Sol critic flagged a failing candidate and the loop did not rescue it, the
  worker had closed every confirmed finding and the hidden tests still failed
  in 18 of 34 cases across the six Sol arms, and in 7 of 8 under runner 0.5:
  there the critic's probes and the hidden tests checked different things.
  Tying every finding to a sentence of the task is the next change to test.

## The arms

| Arm | Models | Runner | Limits | DeepSeek price |
| --- | --- | --- | --- | --- |
| Heavy model alone | `gpt-6-astra`, high reasoning effort | `33e7ccd` | the longest run took 17 calls | |
| Frontier model alone | `gpt-6.1-sol`, high reasoning effort | `9f33aa8` | the longest run took 17 calls | |
| KLP Standard, run 1 | worker `deepseek-flash`, thinking on; critic `gpt-6.1-sol` at its default effort | `9f33aa8` | 40 worker steps, one repair round | standard (peak hours) |
| KLP Standard, run 2 | the same | `33e7ccd` | 100 worker steps, two repair rounds | standard (peak hours) |
| KLP Standard, run 3 | the same | runner 0.5, `f146aef` to `df2e27d` | 100 worker steps, two repair rounds | off-peak, half rate |

Each "worker alone" row below is the candidate its KLP run went on to review,
graded before review. Every critic arm in section 4 reviews one run's recorded
candidates. The settings come from [`models.json`](models.json) and the
[Method](README.md#method).

The three KLP runs are different configurations, not repeats, and each model
alone ran once, so run-to-run spread is measured only for the worker in runs 2
and 3: same settings, 54 and 57 solved. The 66 tasks come from seven base
commits in three repositories, 7 to 12 tasks each. The tests below treat tasks
as independent.

## 1. Is the difference more than chance?

<!-- table:intervals -->
| 66 tasks | Tasks solved | 95% interval |
| --- | ---: | ---: |
| Heavy model alone (`gpt-6-astra`) | 56 (85%) | 74% to 92% |
| Frontier model alone (`gpt-6.1-sol`) | 56 (85%) | 74% to 92% |
| Low-cost worker alone, run 1 | 56 (85%) | 74% to 92% |
| Low-cost worker alone, run 2 | 54 (82%) | 71% to 89% |
| Low-cost worker alone, run 3 | 57 (86%) | 76% to 93% |
| KLP Standard, run 1 | 57 (86%) | 76% to 93% |
| KLP Standard, run 2 | 54 (82%) | 71% to 89% |
| KLP Standard, run 3 | 59 (89%) | 80% to 95% |
<!-- /table:intervals -->

Each interval is a 95% Wilson interval, 15 to 18 points wide with 66 tasks.

Only the tasks where two arms disagree say anything about which is better. For
each pair the table gives that split, its exact McNemar p-value, the split
(either way) that would count as more than chance, and the difference in solve
rate with its 95% interval.

<!-- table:comparisons -->
| Arm | Against | Only the arm solved | Only the other solved | p | Needed for p < 0.05 | Difference in points, 95% interval |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| KLP Standard, run 1 (57) | heavy model alone (56) | 2 | 1 | 1.00 | no split | +1.5 (−5.3 to +8.6) |
| KLP Standard, run 1 (57) | frontier model alone (56) | 3 | 2 | 1.00 | no split | +1.5 (−6.5 to +9.7) |
| KLP Standard, run 1 (57) | its worker alone (56) | 1 | 0 | 1.00 | no split | +1.5 (−3.9 to +7.4) |
| KLP Standard, run 2 (54) | heavy model alone (56) | 3 | 5 | 0.73 | 8 to 0 | −3.0 (−12.5 to +6.2) |
| KLP Standard, run 2 (54) | frontier model alone (56) | 2 | 4 | 0.69 | 6 to 0 | −3.0 (−11.6 to +5.3) |
| KLP Standard, run 2 (54) | its worker alone (54) | 0 | 0 | 1.00 | no split | +0.0 (−4.5 to +4.5) |
| KLP Standard, run 3 (59) | heavy model alone (56) | 5 | 2 | 0.45 | 7 to 0 | +4.5 (−4.3 to +13.8) |
| KLP Standard, run 3 (59) | frontier model alone (56) | 5 | 2 | 0.45 | 7 to 0 | +4.5 (−4.3 to +13.8) |
| KLP Standard, run 3 (59) | its worker alone (57) | 2 | 0 | 0.50 | no split | +3.0 (−3.0 to +9.9) |
| Low-cost worker alone, run 1 (56) | heavy model alone (56) | 2 | 2 | 1.00 | no split | +0.0 (−7.5 to +7.5) |
| Low-cost worker alone, run 1 (56) | frontier model alone (56) | 2 | 2 | 1.00 | no split | +0.0 (−7.5 to +7.5) |
| Low-cost worker alone, run 2 (54) | heavy model alone (56) | 3 | 5 | 0.73 | 8 to 0 | −3.0 (−12.5 to +6.2) |
| Low-cost worker alone, run 2 (54) | frontier model alone (56) | 2 | 4 | 0.69 | 6 to 0 | −3.0 (−11.6 to +5.3) |
| Low-cost worker alone, run 3 (57) | heavy model alone (56) | 4 | 3 | 1.00 | 7 to 0 | +1.5 (−7.5 to +10.6) |
| Low-cost worker alone, run 3 (57) | frontier model alone (56) | 4 | 3 | 1.00 | 7 to 0 | +1.5 (−7.5 to +10.6) |
<!-- /table:comparisons -->

Run 3 and the heavy model disagree on 7 tasks, so only a 7 to 0 split would
count; it was 5 to 2. The difference of +4.5 points could be anything from
about −4 to +14, and run 2's −3.0 anything from −12.5 to +6.2. The worker alone
compares the same way in every run. So read the benchmark as: no detectable
difference in pass rate between KLP Standard, its worker alone and either
model alone, and a large difference in cost.

## 2. Does it hold on bigger tasks?

Task size here is the dataset's reference solution: lines added plus lines
removed. Tasks are ranked by it, ties by task id, and split into three groups
of 22. Four tasks sit at exactly 70 lines, so the medium and large groups
share that value.

<!-- table:size -->
| Tasks solved | Small, 2–40 lines | Medium, 43–70 | Large, 70–232 | One file | Two files |
| --- | ---: | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`) | 20 | 19 | 17 | 34 | 22 |
| Frontier model alone (`gpt-6.1-sol`) | 20 | 18 | 18 | 34 | 22 |
| Low-cost worker alone, run 1 | 19 | 20 | 17 | 34 | 22 |
| Low-cost worker alone, run 2 | 19 | 19 | 16 | 35 | 19 |
| Low-cost worker alone, run 3 | 19 | 20 | 18 | 37 | 20 |
| KLP Standard, run 1 | 19 | 21 | 17 | 35 | 22 |
| KLP Standard, run 2 | 19 | 19 | 16 | 35 | 19 |
| KLP Standard, run 3 | 21 | 20 | 18 | 38 | 21 |
| Tasks in the group | 22 | 22 | 22 | 42 | 24 |
| Tasks no arm solved | 1 | 1 | 3 | 4 | 1 |
| Smallest p between any two arms above | 0.50 | 0.25 | 0.50 | 0.125 | 0.25 |
<!-- /table:size -->

- **No gap between arms is more than chance in any column.** The last row
  gives the smallest exact McNemar p over every pair of the eight arms in that
  group. A gap counts only when one arm leads the tasks the two disagree on by
  at least six: 6 to 0 is the smallest such split, 8 to 1 also counts, 7 to 1
  does not.
- **Every arm solved a little less of the largest third,** 16 to 18 of 22
  against 19 to 21 of the smallest. Three of the five tasks no arm solved are
  in that third and one in the smallest, which alone puts every arm two tasks
  lower on the largest third.
- **Two-file tasks.** Split by files changed, the loop trails the models alone
  only on the 24 tasks whose reference solution changes two files, and only in
  runs 2 and 3: 19 and 21 solved against 22. In run 1 it solved 22. In run 3
  review narrowed the gap by one task; its worker alone solved 20. These 24
  tasks come from three base commits (all of Click task 2068 and dirty-equals
  task 43, three of Click task 2800), so file count cannot be told apart from
  those commits.

By repository:

<!-- table:repositories -->
| Tasks solved | Click (27) | Jinja (30) | dirty-equals (9) |
| --- | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`) | 22 | 27 | 7 |
| Frontier model alone (`gpt-6.1-sol`) | 22 | 27 | 7 |
| Low-cost worker alone, run 1 | 21 | 27 | 8 |
| Low-cost worker alone, run 2 | 20 | 27 | 7 |
| Low-cost worker alone, run 3 | 23 | 28 | 6 |
| KLP Standard, run 1 | 22 | 27 | 8 |
| KLP Standard, run 2 | 20 | 27 | 7 |
| KLP Standard, run 3 | 25 | 28 | 6 |
| Tasks no arm solved | 2 | 2 | 1 |
| Smallest p between any two arms above | 0.0625 | 1.00 | 0.50 |
<!-- /table:repositories -->

The five tasks no arm solved are 40 to 123 lines, and four of them change one
file. For four of them, the hidden tests check something the task statement
does not ask for. Click task 2956 feature 7, for example, passes hyphenated
option names to `conflicts_with`, where the statement's own example uses
`input_text`. In the fifth, Jinja task 1621 feature 4, the statement does ask
for the behaviour ("invalid tuple formats should be handled gracefully"), and
every arm missed it.

**What this benchmark cannot tell you.** Every reference solution here is 2 to
232 lines in one or two files. It says nothing about changes that span many
files or thousands of lines. The [SWE-bench Pro Ansible task](../ansible-workers-2026-10-27/README.md)
is one larger task, not a benchmark.

## 3. Tokens and cost

<!-- table:tokens -->
| Per solved task | Solved | All tokens | Frontier-model tokens | Low-cost-model tokens | Input not read from cache | Share of input read from cache |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`) | 56 | 165k | 165k | 0 | 25k | 84% |
| Frontier model alone (`gpt-6.1-sol`) | 56 | 150k | 150k | 0 | 24k | 83% |
| Low-cost worker alone, run 1 | 56 | 552k | 0 | 552k | 23k | 96% |
| Low-cost worker alone, run 2 | 54 | 762k | 0 | 762k | 25k | 97% |
| Low-cost worker alone, run 3 | 57 | 718k | 0 | 718k | 24k | 97% |
| KLP Standard, run 1 | 57 | 778k | 9.3k | 769k | 33k | 96% |
| KLP Standard, run 2 | 54 | 1.1M | 11k | 1.1M | 38k | 97% |
| KLP Standard, run 3 | 59 | 1.1M | 11k | 1.1M | 36k | 97% |
<!-- /table:tokens -->

The loop uses more tokens than a frontier model working alone: about 1.1
million per solved task in run 3, against 150 thousand, seven times as many
(five times in run 1). Nearly all of them are the low-cost model's, and 97% of
its input comes from cache, which DeepSeek bills at a fiftieth of its uncached
rate. The loop's input not read from cache, worker and critic together, is
about one and a half times the frontier model's. The frontier model's share
falls from 150 thousand tokens per solved task to 11 thousand: one review
packet at a time.

A review arm's figures include the worker run whose candidate it reviewed, the
same way its cost does. Output tokens include reasoning tokens. The table
covers the models alone, the three worker runs and the three KLP runs; the
other critic arms' usage is in [`ledger.jsonl`](ledger.jsonl), where the
critics reached through a subscription CLI report none.

<!-- table:cost -->
| 66 tasks | Solved | Cost per task | Cost per solved task | At DeepSeek's standard rate: per task | Per solved task |
| --- | ---: | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`) | 56 | $0.721 | $0.849 | $0.721 | $0.849 |
| Frontier model alone (`gpt-6.1-sol`) | 56 | $0.123 | $0.146 | $0.123 | $0.146 |
| Low-cost worker alone, run 1 | 56 | $0.024 | $0.028 | $0.024 | $0.028 |
| Low-cost worker alone, run 2 | 54 | $0.027 | $0.034 | $0.027 | $0.034 |
| Low-cost worker alone, run 3 | 57 | $0.014 | $0.016 | $0.028 | $0.033 |
| KLP Standard, run 1 | 57 | $0.055 | $0.064 | $0.055 | $0.064 |
| KLP Standard, run 2 | 54 | $0.061 | $0.074 | $0.061 | $0.074 |
| KLP Standard, run 3 | 59 | $0.046 | $0.051 | $0.064 | $0.071 |
<!-- /table:cost -->

Costs are as billed: provider-reported usage at the rates in
[`prices.json`](prices.json), each call at the tier recorded with it. Run 3's
DeepSeek calls fell in DeepSeek's off-peak hours, at half rate; runs 1 and 2
paid its standard rate. The last two columns reprice every off-peak call at
the standard rate. On that footing:

- KLP Standard costs 11 to 13 times less per task than the heavy model and
  about half as much as the frontier model. As billed, off-peak, run 3 costs a sixteenth
  of the heavy model and 63% less than the frontier model.
- The worker alone costs a twenty-sixth to a thirtieth of the heavy model per
  task, with no detectable difference in pass rate. With review and repair,
  KLP Standard costs 2.2 to 2.3 times the worker alone in every run (3.3 times
  as billed in run 3). So review and repair add 1.2 to 1.3 times the worker's
  own cost, and they added 1, 0 and 2 solved tasks.

Both models alone ran at high reasoning effort. The critic is the frontier
model at its default effort, through chat completions; no arm runs the
frontier model alone at that effort.

## 4. What the critics found

### Settled by a probe

Every blocking finding comes with a probe test. A probe that fails confirms
the finding and, while repair rounds remain, starts a repair; a finding
confirmed in the last review is handed over open. A probe that passes discards
the finding, and one pytest cannot run leaves it unproven.

<!-- table:dispositions -->
| Critic | Settled by a probe | Confirmed: probe failed | Discarded: probe passed | Confirmed share | Advisory or unproven | Withdrawn |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol`, run 3 | 80 | 77 | 3 | 96% | 0 | 0 |
| `gpt-6.1-sol`, run 2 | 80 | 78 | 2 | 98% | 0 | 0 |
| `gpt-6.1-sol`, run 1 | 67 | 64 | 3 | 96% | 0 | 0 |
| `gpt-6.1-sol`, runner 0.5, run 2 candidates | 89 | 86 | 3 | 97% | 0 | 2 |
| `gpt-6-astra`, earlier runner, run 2 candidates | 82 | 81 | 1 | 99% | 0 | 0 |
| `gpt-6.1-terra`, earlier runner, run 2 candidates | 228 | 222 | 6 | 97% | 0 | 0 |
| `grok-4.7`, run 2 candidates | 10 | 4 | 6 | 40% | 0 | 1 |
| Kimi K3.1 Pro (CLI), run 2 candidates | 27 | 16 | 11 | 59% | 0 | 1 |
| Gemini 4 Argon (CLI), run 2 candidates | 5 | 5 | 0 | 100% | 1 | 2 |
| Qwen 3.8 Max (CLI), run 2 candidates | 7 | 3 | 4 | 43% | 138 | 2 |
| `gpt-6.1-sol` + acceptance file, run 2 candidates | 71 | 69 | 2 | 97% | 0 | 1 |
| `gpt-6.1-sol` + acceptance file, run 3 candidates | 61 | 59 | 2 | 97% | 2 | 0 |
<!-- /table:dispositions -->

The Sol critic's probes failed, confirming the finding, 96% to 98% of the
time; the other critics' 40% to 100%. A confirmed finding means the candidate
fails the critic's test. It does not show the test checks what the claim says,
or that the task asks for it, so we measured that two more ways.

### Against the hidden tests

<!-- table:first_review -->
| Critic | Candidates failing the hidden tests | Flagged | Rescued | Candidates passing them | Flagged | Broken |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol`, run 3 | 9 | 5 | 2 | 57 | 30 | 0 |
| `gpt-6.1-sol`, run 2 | 12 | 9 | 0 | 54 | 26 | 0 |
| `gpt-6.1-sol`, run 1 | 10 | 7 | 1 | 56 | 29 | 0 |
| `gpt-6.1-sol`, runner 0.5, run 2 candidates | 12 | 10 | 2 | 54 | 29 | 0 |
| `gpt-6-astra`, earlier runner, run 2 candidates | 12 | 8 | 1 | 54 | 27 | 0 |
| `gpt-6.1-terra`, earlier runner, run 2 candidates | 12 | 10 | 1 | 54 | 41 | 3 |
| `grok-4.7`, run 2 candidates | 12 | 2 | 0 | 54 | 2 | 0 |
| Kimi K3.1 Pro (CLI), run 2 candidates | 12 | 4 | 1 | 54 | 5 | 0 |
| Gemini 4 Argon (CLI), run 2 candidates | 12 | 3 | 2 | 54 | 1 | 0 |
| Qwen 3.8 Max (CLI), run 2 candidates | 11 | 0 | 0 | 52 | 3 | 0 |
| `gpt-6.1-sol` + acceptance file, run 2 candidates | 12 | 7 | 3 | 54 | 22 | 0 |
| `gpt-6.1-sol` + acceptance file, run 3 candidates | 9 | 4 | 0 | 57 | 27 | 0 |
<!-- /table:first_review -->

The table counts each critic's first review of the worker's candidate. In run
3 the candidate failed the hidden tests on 9 tasks; the critic confirmed a
problem on 5 of them and the loop rescued 2. On the 57 candidates that already
passed, the critic still confirmed a problem on 30. The repairs that followed
broke none of them.

### What the receipt said at handover

A run ends `completed` when its last review left no confirmed finding open and
the declared checks passed. A finding still open, a failed check, the time or
spend limit, or a repair rolled back for breaking a check ends it
`budget_exhausted`, and a critic that could not answer ends it `blocked`. The
table counts both of those as ended with something unresolved.

<!-- table:handover -->
| Critic | Ended clean | Solved | Not solved | Ended with something unresolved | Solved | Not solved | Not solved, receipt unresolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol`, run 3 | 58 | 52 | 6 | 8 | 7 | 1 | 1 of 7 |
| `gpt-6.1-sol`, run 2 | 56 | 48 | 8 | 10 | 6 | 4 | 4 of 12 |
| `gpt-6.1-sol`, run 1 | 48 | 43 | 5 | 18 | 14 | 4 | 4 of 9 |
| `gpt-6.1-sol`, runner 0.5, run 2 candidates | 58 | 49 | 9 | 8 | 7 | 1 | 1 of 10 |
| `gpt-6-astra`, earlier runner, run 2 candidates | 57 | 49 | 8 | 9 | 6 | 3 | 3 of 11 |
| `gpt-6.1-terra`, earlier runner, run 2 candidates | 34 | 28 | 6 | 32 | 24 | 8 | 8 of 14 |
| `grok-4.7`, run 2 candidates | 64 | 54 | 10 | 2 | 0 | 2 | 2 of 12 |
| Kimi K3.1 Pro (CLI), run 2 candidates | 65 | 54 | 11 | 1 | 1 | 0 | 0 of 11 |
| Gemini 4 Argon (CLI), run 2 candidates | 66 | 56 | 10 | 0 | 0 | 0 | 0 of 10 |
| Qwen 3.8 Max (CLI), run 2 candidates | 63 | 52 | 11 | 3 | 2 | 1 | 1 of 12 |
| `gpt-6.1-sol` + acceptance file, run 2 candidates | 56 | 50 | 6 | 10 | 7 | 3 | 3 of 9 |
| `gpt-6.1-sol` + acceptance file, run 3 candidates | 60 | 54 | 6 | 6 | 3 | 3 | 3 of 9 |
<!-- /table:handover -->

In run 3 the loop handed over 7 tasks that fail the hidden tests. The receipt
marked 1 of them unresolved; the other 6 ended clean. Of the 8 runs that ended
with something unresolved, 7 passed the hidden tests. On these tasks a clean
receipt means the critic's probes and the declared checks pass, and no more.
The Qwen CLI timed out on 3 reviews, the `blocked` runs in its row; 2 of
those candidates passed the hidden tests.

<!-- table:not_rescued -->
| Critic | Failing candidates flagged | Rescued | Not rescued: every confirmed finding closed | Not rescued: something left unresolved |
| --- | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol`, run 3 | 5 | 2 | 2 | 1 |
| `gpt-6.1-sol`, run 2 | 9 | 0 | 5 | 4 |
| `gpt-6.1-sol`, run 1 | 7 | 1 | 2 | 4 |
| `gpt-6.1-sol`, runner 0.5, run 2 candidates | 10 | 2 | 7 | 1 |
| `gpt-6-astra`, earlier runner, run 2 candidates | 8 | 1 | 4 | 3 |
| `gpt-6.1-terra`, earlier runner, run 2 candidates | 10 | 1 | 3 | 6 |
| `grok-4.7`, run 2 candidates | 2 | 0 | 0 | 2 |
| Kimi K3.1 Pro (CLI), run 2 candidates | 4 | 1 | 3 | 0 |
| Gemini 4 Argon (CLI), run 2 candidates | 3 | 2 | 1 | 0 |
| Qwen 3.8 Max (CLI), run 2 candidates | 0 | 0 | 0 | 0 |
| `gpt-6.1-sol` + acceptance file, run 2 candidates | 7 | 3 | 1 | 3 |
| `gpt-6.1-sol` + acceptance file, run 3 candidates | 4 | 0 | 1 | 3 |
<!-- /table:not_rescued -->

When the critic flagged a candidate that failed the hidden tests and the loop
did not rescue it, the repair often had done what it was asked. Under the
runner 0.5 Sol critic, 7 of the 8 such runs ended with every confirmed finding
closed: the worker fixed what the critic's probes showed, and the hidden tests
still failed. Across the six Sol arms it was 18 of 34; run 1, which allowed one
repair round, left 4 of its 6 unresolved. Where every finding was closed, the
critic's probes and the hidden tests were checking different things. Four of the five tasks no arm solved test behaviour the task statement
does not state, so on those a critic would have had to guess what the hidden
tests check.

### Against the reference solution

Are those 30 real problems, or the critic asking for more than the task needs?
Every task in the dataset ships with a reference solution that passes its
hidden tests. We reran each probe we still had against it, in the same sandbox
with no network, with the command it first ran with
([`bench/probes.py`](../../bench/probes.py)). For the runner 0.5 arms that
command applies the project's own test rules, such as treating warnings as
errors; the earlier runner's probes ran without them, and so did their reruns.
Each probe first reran on the candidate it was written for: all 679 gave the
recorded exit code.

<!-- table:reference -->
| Critic | Confirmed findings rerun | Passes on the reference | Fails there too | Cannot run on it | On candidates passing the hidden tests: passes / fails too / cannot run |
| --- | ---: | ---: | ---: | ---: | ---: |
| `gpt-6.1-sol`, run 3 | 77 of 77 | 29 | 46 | 2 | 24 / 40 / 2 |
| `gpt-6.1-sol`, run 2 | 74 of 78 | 28 | 42 | 4 | 19 / 29 / 3 |
| `gpt-6.1-sol`, run 1 | 61 of 64 | 18 | 40 | 3 | 13 / 31 / 2 |
| `gpt-6.1-sol`, runner 0.5, run 2 candidates | 86 of 86 | 40 | 38 | 8 | 28 / 27 / 7 |
| `gpt-6-astra`, earlier runner, run 2 candidates | 78 of 81 | 33 | 42 | 3 | 24 / 29 / 3 |
| `gpt-6.1-terra`, earlier runner, run 2 candidates | 106 of 222 | 42 | 56 | 8 | 33 / 39 / 8 |
| `grok-4.7`, run 2 candidates | 4 of 4 | 1 | 3 | 0 | 1 / 1 / 0 |
| Kimi K3.1 Pro (CLI), run 2 candidates | 15 of 16 | 9 | 6 | 0 | 5 / 4 / 0 |
| Gemini 4 Argon (CLI), run 2 candidates | 5 of 5 | 1 | 3 | 1 | 0 / 1 / 1 |
| Qwen 3.8 Max (CLI), run 2 candidates | 3 of 3 | 1 | 2 | 0 | 1 / 2 / 0 |
| `gpt-6.1-sol` + acceptance file, run 2 candidates | 69 of 69 | 29 | 37 | 3 | 19 / 26 / 2 |
| `gpt-6.1-sol` + acceptance file, run 3 candidates | 59 of 59 | 19 | 38 | 2 | 15 / 30 / 1 |
<!-- /table:reference -->

- **Passes on the reference:** the candidate differed from the reference
  solution in a way the hidden tests do not check.
- **Fails there too:** the critic holds the code to a stricter reading of the
  task than the reference does, the reference shares the defect, or the probe
  is wrong.
- **Cannot run on it:** the reference run's output names a missing import,
  name, attribute or keyword, usually one only the candidate defines. This is
  a text match, so it misfiles a handful of rows both ways: about nine here
  did reach their check on the reference and failed it, and about seven under
  "Fails there too" stopped on a missing name first. None of them is in the
  first column.

About four in ten of the Sol critic's confirmed findings pass on the reference
solution (163 of 426), 57% fail there too and 5% cannot run. The share that
passes is only a little higher on candidates that had failed the hidden tests.

Some confirmed findings are wrong, and the probe gate let them through:

- Six probes, in five critic arms, build `click.Command(..., shell_complete=...)`.
  `Command` takes no such argument, so each probe fails on its own `TypeError`,
  on the candidate and the reference alike.
- An acceptance test on Jinja task 1621 feature 3 (`gpt-6.1-sol` + acceptance
  file, run 3 candidates) requires `a:b` to be a valid template path. The task
  says a path beginning with a letter and a colon must be rejected, and the
  reference rejects it. The critic's next review flagged the repair this
  finding caused.

Two of the findings that fail on the reference, from run 3:

- Adding `batch_size` ahead of `count` in `Option`'s parameters breaks a call
  that passes `count` by position. The reference solution makes the same
  change, so the probe fails there too. That candidate had passed the hidden
  tests.
- The editor-timeout task says that when the timeout is reached "the editor
  process is terminated". The probe starts an editor that keeps working for
  two seconds and checks, after a one-second timeout, that it has stopped. It
  had not on the candidate, and it has not on the reference solution either.
  That candidate had failed the hidden tests; the repair that followed made it
  pass them.

We have not sorted the rest by hand. [`probes.json`](probes.json) lists every
probed finding with its claim, and the 679 we could rerun with their probe and
both reruns, so you can.

**What we take from it.** The probe gate stops a critic from confirming a
problem it cannot reproduce on the candidate. It does not check that the probe
tests what the claim says, or that the task asks for it. Those findings cost
repair money; under a Sol critic they never broke a passing task. The
acceptance-file option already asks the critic to quote the sentence of the
task each test checks; holding every probe to a sentence of the task is the
next thing to test.

129 of the 808 probes could not be rerun, because a later review wrote a new
probe under the same file name; 118 of them are in the earlier runner's
`gpt-6.1-terra` arm. The "Confirmed findings rerun" column shows how many each
critic kept.

## Check it yourself

```bash
python3 case-studies/feature-benchmark-2026-11-10/verify.py      # every table on this page, offline
python3 -m bench.features prepare --work ~/klp-bench            # about 2 minutes, no API keys
python3 -m bench.probes reference --work ~/klp-bench \
  --pack case-studies/feature-benchmark-2026-11-10/probes.json   # rerun every probe on the reference
```

- [`analysis.py`](analysis.py) computes every table from
  [`results.json`](results.json), [`ledger.jsonl`](ledger.jsonl),
  [`report.json`](report.json), [`prices.json`](prices.json),
  [`task-sizes.json`](task-sizes.json) and [`probes.json`](probes.json), and
  writes [`analysis.json`](analysis.json).
- [`task-sizes.json`](task-sizes.json) gives each task's reference solution
  and hidden tests in files and lines, from
  `python3 -m bench.features sizes --work ~/klp-bench`.
- Intervals are Wilson score intervals at 95%. Paired comparisons use the
  exact two-sided McNemar test; the difference between two arms uses
  Newcombe's hybrid score interval for paired outcomes, with his correction
  to the correlation term.
