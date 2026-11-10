# A SWE-bench Pro Task Solved for $0.60: 91% Less Than the Other Worker

**DeepSeek Flash completed a SWE-bench Pro Ansible task with independent review
for $0.5965 in measured API cost, including its share of planning. Gemini Flash
also solved it after a runner repair, for $6.5882 on the same allocation basis.**

Both ran under KLP with the same frozen plan and the Semiotic Protocol, so the
comparison isolates the choice of worker. The Gemini figure is its follow-up run
on a repaired context runner. Measured 27 October 2026.

## A Real Public Coding Task

The task adds opt-in offline collection installation to Ansible: use local
artifacts and installed dependencies without contacting distribution servers,
while preserving normal online behavior. It spans CLI arguments, dependency
resolution, API access and compatibility, rather than a miniature coding puzzle.

The frozen repository contained **5,501 tracked files / 29,661,093 bytes**.
Workers started with **17,482 bytes of selected source context**, not the whole
repository, and could inspect other relevant source. Exact task, revision,
image, source ranges, models and limits are in [inputs.json](inputs.json).

## Results That Earned Acceptance

| Measure | DeepSeek Flash | Gemini Flash, repaired-runner follow-up |
| --- | ---: | ---: |
| Official verifier | Solved, 1.0 | Solved, 1.0 |
| Independent OpenAI critic | PASS | PASS after repair |
| Formal repairs | 0 | 1 |
| Final source tests passing | 207 | 226 |
| Worker calls | 39 | 184 |
| Critic calls | 6 | 21 |
| Worker API USD | 0.065642292 | 4.571003025 |
| Critic API USD | 0.2221440 | 1.7084441 |
| Equal reference plan allocation USD | 0.30872125 | 0.30872125 |
| Allocated workflow API USD | **0.596507542** | **6.588168375** |
| Active coding/check/review time | **6m 10s** | **38m 33s** |

Active time excludes planning, environment setup, official grading and close-out.
Each workflow carries 293.39 seconds of reference planning separately. Gemini
added more tests of its own; both candidates were judged solved by the same
pinned official task verifier.

The Gemini critic found three task-related problems: ignored role requirements
could trigger network discovery; remote transitive metadata could be fetched
before offline rejection; and double normalization could break explicitly
sourced installed dependencies. One worker repair addressed them. The final
critic passed, then the frozen candidate passed official grading.

The lesson is practical: **a cheaper worker can produce a verified solution;
pay for independent checking, and choose from completed outcomes, not model
reputation or token prices alone.** DeepSeek remains our choice for this
workflow.

## The Unsuccessful Work Is Still in the Ledger

Before either worker started, a planning attempt exhausted Claude's 8,192-token
output allowance. We retained that failure and increased the benchmark planning
allowance to 16,384 for a separately approved attempt. The resulting six-call
plan was shared unchanged by both workers. The later Gemini run reused it,
without paying for or billing that plan again.

Gemini's first coding attempt then hit the runner's 512 KiB serialized-request
guard before review. It spent **$1.122118125 on 78 worker calls** and its partial
patch was officially unsolved. That was a runner limit, and the follow-up shows
the model solving the task once it was lifted.

Provider reasoning signatures occupied much of that request. The reviewed
repair preserved those signatures, separated text from trusted opaque provider
metadata, and retained finite transport and spending bounds. The follow-up
successfully sent requests above the old ceiling. No benchmark was repaired
mid-run, no hidden test feedback reached a worker, and the old failure was not
overwritten. The follow-up required its own 205 calls and $6.279447125.

| Included work, charged once | Calls | API USD |
| --- | ---: | ---: |
| Gemini connection/tool qualification | 2 | 0.00061425 |
| Failed shared planning | 5 | 0.4271040 |
| Successful shared planning | 6 | 0.6174425 |
| DeepSeek coding and review | 45 | 0.287786292 |
| First Gemini coding attempt | 78 | 1.122118125 |
| Gemini follow-up coding and review | 205 | 6.279447125 |
| **All included Ansible work** | **341** | **8.734512292** |

Earlier, separate experiments bring the wider experiment ledger to
**$13.178840304 of a $50 budget**. This packet verifies the 341 Ansible calls.
The successful plan cost $0.6174425 once and is allocated equally across the
workflows that used it.

Prices are calculated from provider-reported usage at the recorded rates.
DeepSeek's recorded tariff is off-peak; cache effects remain in each
receipt. Gemini thinking tokens are included even where the compatibility
endpoint's completion count excludes them. Raw input, cache writes, cache hits
and output are charged separately without double counting.

## The Semiotic Protocol Was in the Execution Path

The public adapter and durable wake runner dispatched the workers and critics. The Gemini follow-up recorded:

- Four dispatches: initial worker, initial critic, repair worker, final critic.
- Four transport reads, 3,648 bytes, and zero repeated polling waits.
- **Zero model calls for coordination.**

Both worker configurations used the same adapter. The
[four-scenario coordination comparison](../semio-coordination-2026-10-20/README.md)
measures the adapter's own saving: 75% fewer coordination input tokens.

## Coordinator Effort

Setup, runner repairs and oversight are recorded too. Coordinator checkpoint
usage is published in [receipts.json](receipts.json):

| Phase | Cumulative coordinator input | Cached subset | Output |
| --- | ---: | ---: | ---: |
| Failed preparation | 10,689,853 | 10,513,024 | 48,054 |
| Initial comparison | 17,812,160 | 17,446,144 | 33,235 |
| Gemini follow-up | 16,354,446 | 16,073,728 | 46,700 |

These are cumulative input counts across coordinator turns. Readiness-reviewer
usage is included in the JSON. The coordinator ran on a subscription, so its
effort is reported in tokens.

Three disposable servers added an estimated **EUR0.3366** of hosting in total.
All of them were deleted and checked afterwards. Worker containers had no
external network and no keys.

## Check It Yourself

From the repository root, Python 3.12+ and no API keys:

```bash
python3 case-studies/ansible-workers-2026-10-27/verify.py
python3 -m unittest discover -s case-studies/ansible-workers-2026-10-27 -p 'test_verify.py' -v
```

The verifier recomputes all 341 call costs, retained failures, role totals,
reference allocations and cumulative accounting. It checks the frozen plan
hash and the recorded coordination counts, and rejects missing calls and
changed totals.

The [reproduction guide](REPRODUCE.md) gives the pinned public inputs and
workflow recipe for a new independent run. The [exact frozen plan](frozen-plan.md)
is included, so your run can start from the same plan.
