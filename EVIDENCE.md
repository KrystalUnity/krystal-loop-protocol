# Measured Results

Krystal Unity's own measurements of KLP and the Semiotic Protocol, taken
between 19 October and 10 November 2026. Each result names what was compared
and links to receipts you can recompute. The feature benchmark can be rerun
from this repository with your own keys.

## Feature Benchmark: More Tasks Solved Than the Heavy Model, at a Sixteenth of Its Cost

Sixty-six feature tasks in Click, Jinja and dirty-equals, each graded by tests
the models never see. Every arm had the same task statement, sandbox and shell
tool. 1,056 runs and 9,788 model calls.

| | Tasks solved | Cost per task | Cost per solved task | Whole benchmark |
| --- | ---: | ---: | ---: | ---: |
| Heavy model alone (`gpt-6-astra`, high reasoning) | 56 of 66 | $0.721 | $0.849 | $47.57 |
| Frontier model alone (`gpt-6.1-sol`, high reasoning) | 56 of 66 | $0.123 | $0.146 | $8.15 |
| **KLP Standard, run 3** (runner 0.5, `deepseek-flash` worker, `gpt-6.1-sol` critic) | **59 of 66** | **$0.046** | **$0.051** | **$3.02** |
| KLP Standard, run 2 (two repair rounds) | 54 of 66 | $0.061 | $0.074 | $4.00 |
| KLP Standard, run 1 (one repair round) | 57 of 66 | $0.055 | $0.064 | $3.64 |
| Low-cost worker alone, runs 1 / 2 / 3 | 56 / 54 / 57 of 66 | $0.024 / $0.027 / $0.014 | $0.028 / $0.034 / $0.016 | $1.59 / $1.81 / $0.93 |

Run 3 solved three more tasks than either model working alone and cost 94%
less per task than the heavy model and 63% less than the frontier model. Over
the three runs KLP Standard cost 92% to 94% less than the heavy model and 51%
to 63% less than the frontier model. Each KLP row is the same worker runs as
the worker row, graded before and after review, so the difference is the
review:

- the critic confirmed 64, 78 and 77 findings by running a failing test
  against the candidate;
- 43, 67 and 70 of them were fixed and verified before handover (67%, 86% and
  91%);
- review rescued one failing task in run 1 and two in run 3, and no repair
  broke a passing task in any run.

Runner 0.5 runs each probe under the project's own test rules and keeps a
confirmed finding open until its probe passes. On the identical run 2
candidates, the same critic went from 54 solved to 56 at the same cost.

Critics compared on identical candidates: `gpt-6.1-sol` solved 56 at $0.060 a
task. Gemini 4 Argon, reached through a CLI subscription, also solved 56, with
no metered review cost: $0.028 a task. Kimi K3.1 Pro on its CLI subscription
solved 55. `grok-4.7` solved 54 at $0.058. With
the earlier runner the heavier `gpt-6-astra` solved 55 at $0.165, and the
lighter `gpt-6.1-terra` solved 52 at $0.075 and broke three passing
candidates.

Five of the 66 tasks were failed by every arm; their hidden tests check
behaviour the written specification does not state.

Read the [case study](case-studies/feature-benchmark-2026-11-10/README.md),
recompute it with the [offline checker](case-studies/feature-benchmark-2026-11-10/verify.py),
or [run it yourself](bench/README.md).

## Paired Features: Two Low-Cost Workers and Semio Beat the Frontier Model Alone

Thirty pairs of features whose reference patches conflict when merged. Two
`deepseek-flash` workers each built one feature under KLP Standard, and Semio
carried the handover that brought both into one tree.

| | Pairs passing both hidden test sets | Cost per pair |
| --- | ---: | ---: |
| Frontier model alone, both features (`gpt-6.1-sol`) | 22 of 30 | $0.196 |
| **Two workers under KLP Standard, integrated through Semio** | **28 of 30** | **$0.103** |

On the same finished features, Semio was compared with agent-managed chat,
where both workers are woken and agree in free text who integrates:

| Integration of 30 conflicting pairs | Agent-managed chat | Semio |
| --- | ---: | ---: |
| Pairs passing | 28 | 28 |
| Model calls | 581 | **333** |
| Worker sessions woken | 60 | **28** |
| Integration cost | $0.567 | **$0.222** |

Semio settled two pairs with no model call and woke one worker for each of the
others, with the peer's exact artifact. Plain git merge passed 2 of 30.

Read the [case study](case-studies/paired-features-2026-11-10/README.md) and
recompute it with the [offline checker](case-studies/paired-features-2026-11-10/verify.py).

## One Command on the Public Challenge: One Cent, Half a Minute

`klp run` on the [public challenge task](https://github.com/KrystalUnity/klp-public-challenge),
a filtered-pagination repair with 17 acceptance checks: the DeepSeek worker
built the fix, the frontier critic reviewed it once and passed it, and all 17
checks passed. The run cost $0.011 and took 32 seconds.

## A SWE-bench Pro Task: Solved for $0.60 Where Another Worker Cost $6.59

A pinned public SWE-bench Pro task in Ansible, a repository of 5,501 files:
add opt-in offline collection installation across the CLI, dependency
resolution and API access. A DeepSeek Flash worker under KLP, with independent
OpenAI review, delivered a solution the official verifier scored as solved.
Gemini Flash ran through the same loop from the same plan and also solved it.

| Measure | DeepSeek Flash | Gemini Flash |
| --- | ---: | ---: |
| Official verifier | Solved | Solved |
| Independent critic | PASS | PASS after one repair |
| Workflow API cost, including an equal planning share | **$0.597** | $6.588 |
| Active coding, checking and review time | **6m 10s** | 38m 33s |
| Worker calls | 39 | 184 |

The DeepSeek workflow cost 91% less and finished six times sooner. On the
Gemini candidate the critic found three task-related problems, one repair
closed them, and the candidate then passed official grading. The Semiotic
Protocol dispatched every worker and critic: four dispatches, four transport
reads and no model calls for coordination.

Read the [case study](case-studies/ansible-workers-2026-10-27/README.md), the
[341 call receipts](case-studies/ansible-workers-2026-10-27/receipts.json), the
[offline checker](case-studies/ansible-workers-2026-10-27/verify.py) and the
[reproduction specification](case-studies/ansible-workers-2026-10-27/REPRODUCE.md).

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
