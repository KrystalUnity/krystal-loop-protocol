# Measured Results

Krystal Unity's own measurements of KLP and the Semiotic Protocol, taken
between 19 October and 10 November 2026. Each result names what was compared
and links to receipts you can recompute. The feature benchmark can be rerun
from this repository with your own keys.

## Feature Benchmark: Frontier Solve Rate at a Thirteenth of the Heavy Model's Cost

Sixty-six feature tasks in Click, Jinja and dirty-equals, each graded by tests
the models never see. Every arm had the same task statement, sandbox and shell
tool.

| | Tasks solved | Cost per task | Cost per solved task | Whole benchmark |
| --- | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`, high reasoning) | 56 of 66 | $0.721 | $0.849 | $47.57 |
| Frontier model alone (`gpt-6.1-sol`, high reasoning) | 56 of 66 | $0.123 | $0.146 | $8.15 |
| Low-cost worker alone (`deepseek-flash`) | 56 of 66 | $0.024 | $0.028 | $1.59 |
| **KLP Standard** (that worker, `gpt-6.1-sol` critic, one bounded repair) | **57 of 66** | **$0.055** | **$0.064** | **$3.64** |

KLP Standard cost 92% less per task than the heavy model alone and 55% less
than the frontier model alone, and solved one more task than either. The
low-cost worker alone and KLP Standard are the same worker runs, graded before
and after review, so the difference between those rows is the review:

- the critic confirmed 64 findings by running a failing test against the
  candidate, and 3 more were discarded when their test passed;
- 43 of the 44 findings sent to the one bounded repair were fixed and verified;
- one task went from failing its hidden tests to passing them;
- all 56 candidates that passed before review still passed after it.

The low-cost model made 94% of the KLP calls. The frontier model was called
102 times, once per review, on a packet with a median size of 14.5 KB. All 198
runs and 2,981 calls completed.

Read the [case study](case-studies/feature-benchmark-2026-11-10/README.md),
recompute it with the [offline checker](case-studies/feature-benchmark-2026-11-10/verify.py),
or [run it yourself](bench/README.md).

## One Command on the Public Challenge: One Cent, Half a Minute

`klp run` on the [public challenge task](https://github.com/KrystalUnity/klp-public-challenge),
a filtered-pagination repair with 17 acceptance checks: the DeepSeek worker
built the fix, the frontier critic reviewed it once and passed it, and all 17
checks passed. The run cost $0.011 and took 32 seconds.

## Semio: 75% Fewer Coordination Input Tokens

**Four coordination model calls became one. Both paths handled all four
scenarios correctly.** The Semio adapter settled duplicate, stale and
already-attempted notifications in software, so only the one valid handover
reached the model.

| Coordination metric | Agent-managed handovers | Semio-backed |
| --- | ---: | ---: |
| Model calls | 4 | **1** |
| Reported input tokens | 5,325 | **1,331** |
| Correct scenario outcomes | 4/4 | **4/4** |
| Serialized API request bytes | 22,004 | 5,498 |
| Observed API cost | $0.0169565 | $0.0021088 |

The comparison used the same coding artifact, evidence and coordination model.
A DeepSeek worker repaired the task and an OpenAI critic reviewed it; all 15
frozen checks and six regressions passed. With cache effects equalized, the
coordination API cost is 68.77% lower.

Read the [case study and method](case-studies/semio-coordination-2026-10-20/README.md),
the [seven receipts](case-studies/semio-coordination-2026-10-20/receipts.json)
and the [offline arithmetic check](case-studies/semio-coordination-2026-10-20/verify.py).

## Semio in Daily Use: 69 Agent Sessions on One Bus

Krystal Unity coordinates its own development over one Semio stream. Across
four days it carried 440 coordination messages from 69 agent sessions built on
four model families, in 310 threads, including 43 independent review verdicts
passed between worker and critic sessions. The median message is 704 bytes,
and 142 messages point to a durable handover for the detail.

Read the [case study](case-studies/semio-live-bus-2026-11-10/README.md).

## A Real Coding Repair: 24.6% Lower Total Cost

A notification-retrieval repair in a frozen KrystalView snapshot of 255 files.
All three final candidates passed the same 15 checks, their regression suites
and a fresh final review.

| Measured API cost | Conventional frontier | Frontier KLP | DeepSeek KLP |
| --- | ---: | ---: | ---: |
| Worker, including repair | $0.201606 | $0.160661 | $0.010199 |
| In-loop critic | $0.000000 | $0.104168 | $0.102805 |
| Equal share of readiness and final evaluation | $0.157923 | $0.157923 | $0.157923 |
| Total | **$0.359529** | **$0.422751** | **$0.270926** |

The DeepSeek worker cost 94.94% less than the conventional worker, and the
whole DeepSeek KLP workflow cost 24.64% less than the conventional frontier
workflow.

Read the [case study](case-studies/krystalview-2026-10-20/README.md), the
[55 call receipts](case-studies/krystalview-2026-10-20/receipts.json) and the
[offline arithmetic check](case-studies/krystalview-2026-10-20/verify.py).

## Compact Context Packets: 21% Fewer Input Tokens

One documentation assignment was run twice with the same mission, task and
source facts: once with an eight-document reference bundle, once with the three
relevant documents selected. Each run used a worker, an independent critic, one
repair and a recheck, and both passed final review.

| Metric, including repair and recheck | Full | Compact | Reduction |
| --- | ---: | ---: | ---: |
| Worker input tokens | 81,409 | 59,789 | 26.56% |
| Combined worker and critic input tokens | 104,544 | 82,601 | 20.99% |
| Supplied prompt bytes | 330,377 | 181,099 | 45.18% |

An earlier source-review pilot of three paired cases classified 12 of 12
obligations correctly in both modes and used 24.63% fewer input tokens
(91,017 to 68,601) with compact packets. The accepted guide is the
[compact packet guide](examples/semio-coordination/CONTEXT_PACKETS.md).

## Event Wake: 3 Transport Reads Instead of 21

Waiting for a handover by event took 3 transport reads; polling for the same
handover took 21. Both jobs completed and refused a second launch after
reopening their retained receipts. The bridge is in
[commit b244990](https://github.com/KrystalUnity/krystal-loop-protocol/commit/b2449906af604eb203944b3332bb163c5c7c58dc).

## How the Savings Work

- **Model routing with a safety net.** The low-cost model does the many turns
  of reading, editing and testing. The frontier model reads one compact packet
  per task.
- **Evidence instead of debate.** A finding is confirmed or discarded by
  running its probe, so repairs are spent only on demonstrated problems.
- **Software for the routine decisions.** Semio gives messages explicit types,
  task identities and artifact revisions, so duplicates and stale notices are
  settled without a model call.
- **Bounded loops.** Cost, step and repair limits are enforced by the runner,
  and every run ends with a receipt.

Each figure on this page measures the comparison named in its own section.
Costs are calculated from provider-reported token usage at the recorded API
rates.
