# A Second Look at the 66-Task Benchmark

KLP Standard matched the heavy model's pass rate for a sixteenth of its cost.
Readers pushed on that result with four questions: is the gap more than
chance, does it hold on bigger tasks, how many tokens does it burn, and are
the critic's findings real? This page answers each one from the published
receipts, with no new model calls. Every table recomputes offline:

```bash
python3 case-studies/feature-benchmark-2026-11-10/verify.py
```

## In short

- **Same pass rate, a sixteenth of the cost.** Run 3 solved 59 tasks and the
  heavy model 56. They disagree on only 7 tasks, 5 to 2 in the loop's favour,
  which is well within chance (p = 0.45). Across three runs the loop solved 54
  to 59 and its worker alone 54 to 57. The result that holds is the price:
  $0.051 per solved task against $0.849.
- **No size effect shows up, and these tasks are small.** Every arm drops a
  little on the largest third of tasks. The loop is weakest where the reference
  solution touches two files. No gap between arms is bigger than chance, and
  no task here is bigger than 232 changed lines in two files.
- **More tokens, cheaper tokens.** The loop reads about seven times as many
  tokens per solved task as the frontier model alone. Almost all of them are
  the low-cost model's, and 97% of its input comes from cache. Frontier-model
  tokens per solved task fall from 150 thousand to 11 thousand.
- **Every confirmed finding is real behaviour; not every one is required.**
  All 679 probes we could rerun reproduced their recorded result exactly. On
  the dataset's reference solution, about four in ten of the Sol critic's
  confirmed findings pass and the rest fail there too. Those repairs cost
  money but never broke a passing task.

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

Each interval is a 95% Wilson interval. With 66 tasks it spans 15 to 18
points, wider than any gap between the arms.

Only the tasks where two arms disagree say anything about which is better. The
last column is the split those tasks would need before the gap counts as more
than chance, by the exact McNemar test.

<!-- table:comparisons -->
| KLP Standard | Against | Only the loop solved | Only the other solved | p | Needed for p < 0.05 |
| --- | --- | ---: | ---: | ---: | ---: |
| Run 1 (57) | heavy model alone (56) | 2 | 1 | 1.00 | no split |
| Run 1 (57) | frontier model alone (56) | 3 | 2 | 1.00 | no split |
| Run 1 (57) | its worker alone (56) | 1 | 0 | 1.00 | no split |
| Run 2 (54) | heavy model alone (56) | 3 | 5 | 0.73 | 8 to 0 |
| Run 2 (54) | frontier model alone (56) | 2 | 4 | 0.69 | 6 to 0 |
| Run 2 (54) | its worker alone (54) | 0 | 0 | 1.00 | no split |
| Run 3 (59) | heavy model alone (56) | 5 | 2 | 0.45 | 7 to 0 |
| Run 3 (59) | frontier model alone (56) | 5 | 2 | 0.45 | 7 to 0 |
| Run 3 (59) | its worker alone (57) | 2 | 0 | 0.50 | no split |
<!-- /table:comparisons -->

Run 3 and the heavy model disagree on 7 tasks, so only a 7 to 0 split would
count; it was 5 to 2. The worker alone moved by three tasks between runs with
nothing changed, the same as the loop's best margin over the heavy model. So
read the benchmark as: the loop matches a frontier model's pass rate, and the
cost difference is the result.

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
<!-- /table:size -->

- **Larger tasks are harder for every arm,** the loop included: 16 to 18 of
  the largest 22, against 19 to 21 of the smallest.
- **The loop is weakest on tasks whose reference solution changes two files.**
  Both frontier models solved 22 of 24. The loop solved 19 to 22 across its
  runs, the same as its worker alone, so review did not close that gap. The
  loop's extra solves came from one-file tasks: 35 to 38 of 42, against 34.
- **None of these gaps is more than chance.** Within a group of 22, one arm
  would have to solve six tasks the other missed, and miss none the other
  solved, before a gap counted.

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
<!-- /table:repositories -->

The five tasks every arm missed are 40 to 123 lines, and four of them change
one file. Their hidden tests check behaviour the written task does not state.

**What this benchmark cannot tell you.** Every reference solution here is 2 to
232 lines in one or two files. It says nothing about changes that span many
files or thousands of lines. The [SWE-bench Pro Ansible task](../ansible-workers-2026-10-27/README.md)
is one larger task, not a benchmark.

## 3. Tokens per solved task

<!-- table:tokens -->
| 66 tasks | Solved | Tokens per solved task | Frontier-model tokens | Low-cost-model tokens | Fresh input | Input read from cache | Cost per solved task |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`) | 56 | 165k | 165k | 0 | 25k | 84% | $0.849 |
| Frontier model alone (`gpt-6.1-sol`) | 56 | 150k | 150k | 0 | 24k | 83% | $0.146 |
| Low-cost worker alone, run 1 | 56 | 552k | 0 | 552k | 23k | 96% | $0.028 |
| Low-cost worker alone, run 2 | 54 | 762k | 0 | 762k | 25k | 97% | $0.034 |
| Low-cost worker alone, run 3 | 57 | 718k | 0 | 718k | 24k | 97% | $0.016 |
| KLP Standard, run 1 | 57 | 778k | 9.3k | 769k | 33k | 96% | $0.064 |
| KLP Standard, run 2 | 54 | 1.1M | 11k | 1.1M | 38k | 97% | $0.074 |
| KLP Standard, run 3 | 59 | 1.1M | 11k | 1.1M | 36k | 97% | $0.051 |
<!-- /table:tokens -->

The loop reads more tokens than a frontier model working alone: about 1.1
million per solved task in run 3, against 150 thousand. Nearly all of them are
the low-cost model's, and 97% of its input comes from cache, which DeepSeek
bills at a fraction of its fresh rate. Fresh input, the part billed at full
rate, is about one and a half times the frontier model's. The frontier model's
share falls from 150 thousand tokens per solved task to 11 thousand: one
review packet at a time.

A review arm's figures include the worker run whose candidate it reviewed, the
same way its cost does. Output tokens include reasoning tokens. Critics reached
through a subscription CLI do not report tokens, so those arms are left out
here.

## 4. What the critics found

### Settled by a probe

Every blocking finding comes with a probe test. A probe that fails confirms
the finding and starts a repair; a probe that passes discards it.

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
time. That shows the critic rarely reports a problem it cannot demonstrate. It
does not show the problem matters, so we measured that two more ways.

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

### Against the reference solution

Are those 30 real problems, or the critic asking for more than the task needs?
Every task in the dataset ships with a reference solution that passes its
hidden tests. We reran every probe we still had against it, in the same
sandbox with no network, under the project's own test rules
([`bench/probes.py`](../../bench/probes.py)). Each probe first reran on the
candidate it was written for: all 679 gave the recorded result.

<!-- table:reference -->
| Critic | Confirmed findings rerun | Reference agrees | Asks for more | Cannot run on it | On candidates passing the hidden tests: agrees / asks for more / cannot run |
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

- **Reference agrees:** the probe passes on the reference solution, so the
  candidate really did differ from the intended behaviour.
- **Asks for more:** the probe fails on the reference solution too. Either
  the critic holds the code to a stricter reading of the task than the
  reference does, or the reference shares the defect.
- **Cannot run on it:** the probe relies on a name only the candidate
  defines, so it proves nothing about the reference.

About four in ten of the Sol critic's confirmed findings match the reference
solution. The share is only a little higher on candidates that had failed the
hidden tests. Two of the findings that ask for more, from run 3:

- The editor-timeout task says that when the timeout is reached "the editor
  process is terminated". The probe starts an editor that keeps working for
  two seconds and checks, after a one-second timeout, that it has stopped. It
  had not on the candidate, and it has not on the reference solution either.
- Adding `batch_size` ahead of `count` in `Option`'s parameters breaks a call
  that passes `count` by position. The reference solution makes the same
  change, so the probe fails there too.

We have not sorted the rest by hand. [`probes.json`](probes.json) lists every
finding with its claim, its probe and both reruns, so you can.

**What we take from it.** The probe gate stops a critic from inventing bugs:
every confirmed finding is real behaviour in the code. It does not stop a
critic asking for more than the task needs. Those repairs cost money, never a
passing task: no repair under a Sol critic broke one. The acceptance-file
option already asks the critic to quote the sentence of the task each test
checks; holding every probe to a sentence of the task is the next thing to
test.

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
  [`task-sizes.json`](task-sizes.json) and [`probes.json`](probes.json), and
  writes [`analysis.json`](analysis.json).
- [`task-sizes.json`](task-sizes.json) gives each task's reference solution
  and hidden tests in files and lines, from
  `python3 -m bench.features sizes --work ~/klp-bench`.
- Intervals are Wilson score intervals at 95%. Paired comparisons use the
  exact two-sided McNemar test.
