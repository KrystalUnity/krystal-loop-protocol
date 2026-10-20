# Four Agent Calls Became One

**75% fewer coordination input tokens. All four scenarios handled correctly.**

On 20 October 2026, we compared agent-managed handovers with KLP's optional
Semio coordination adapter. Both paths used the same real coding artifact,
the same evidence and the same coordination model.

Semio handled three notifications mechanically before they reached the model.
The model still handled the valid new handover. The result:

| Coordination metric | Agent-managed | Semio-backed |
| --- | ---: | ---: |
| Model calls | 4 | **1** |
| Input tokens | 5,325 | **1,331** |
| Correct outcomes | 4/4 | **4/4** |
| Serialized API request bytes | 22,004 | 5,498 |

This is the practical benefit: spend model turns on work that needs a model,
not on deciding whether the same completed job should run again.

## What Ran

A DeepSeek Flash worker repaired a real stored-null notification compatibility
defect in an isolated KrystalView candidate. Before the repair, the regression
suite had one failure and five passes. Afterwards, **all six regressions and
15 unchanged frozen checks passed**.

A fresh OpenAI GPT-6 Astra critic reviewed the helper, regression source and
check output and returned PASS. Worker and critic were from different model
families. The coordinator executed the checks in disposable PostgreSQL and
isolated filesystem/network namespaces; the critic did not independently
execute tests or inspect every route.

That assignment ran once. Its artifact and compact evidence packet were shared
across the two coordination replays, avoiding differences in coding output.
Both used GPT-6.1 Sol with high reasoning for coordination; worker and critic
also used high reasoning. The clean-event API request bodies were byte-for-byte
identical. These are recorded test-date model identities, not model recommendations.

## The Four Scenarios

| Incoming event | Agent-managed path | Semio-backed path | Required outcome |
| --- | --- | --- | --- |
| Valid new handover | Model triage | Model triage | Request one bounded review |
| Identical duplicate after completion | Model triage | Adapter deduplication | Do not repeat work |
| Stale artifact revision | Model triage | Binding rejection | Reject stale work |
| Reopen after claim, before acknowledgement | Model triage | Durable attempt guard | Reconcile without relaunch |

**Both paths got all four right. Semio used one model call instead of four.**

The baseline had concise handovers, exact task/artifact identities, durable
job records and explicit instructions to avoid repeat work. It used fresh
context for each event, with no polling, padded history or extra source reads.
Its runner sent each event to a model; Semio checked eligibility first.

The existing public `SemioAdapter` and `WakeRunner` ran unmodified with a
local replay transport. Stale work stopped the consumer without advancing its
cursor. The restart fixture retained its claimed attempt and pending message,
and refused a second callback. Restart was simulated in a separate fixture,
not by skipping past the stale event. Replay callbacks referred to the single
shared review; they did not launch additional paid critics.

## Costs, Including the Shared Work

USD calculated from provider-reported usage and recorded test-date rates,
including cache writes, cache reads and output:

| Cost | Agent-managed | Semio-backed |
| --- | ---: | ---: |
| Coordination API | $0.0169565 | $0.0021088 |
| Equal share of worker and critic | $0.0494475 | $0.0494475 |
| **API total with shared assignment** | **$0.0664040** | **$0.0515563** |

The worker cost $0.001065 and the critic $0.097830. The complete experiment
cost **$0.1179603 across seven inference calls**, with no retries, failed
provider calls or missing usage receipts. The shared assignment is split
equally, not claimed as two independently executed coding runs.

### Separating Cache Effects

Semio's clean call followed the identical baseline request and received a
warm cache. Therefore the observed **87.56% coordination API reduction** and
**22.36% reduction including shared work** include a cache advantage.

Price Semio's clean input at the baseline's identical input cost, keeping its
actual output, and its coordination cost becomes **$0.0052960: 68.77% lower**.
Including the equal shared allocation gives **$0.0547435 versus $0.0664040:
17.56% lower**. This is a cache-equalized sensitivity calculation, not another
live experiment. The seven receipts support both calculations.

The clean event itself used 1,331 input tokens in each path. The 75% input
saving came from removing three unnecessary model calls, not from shrinking
the valid handover or from cache accounting.

## Effort and Comparison Boundaries

- The adapter's 27 existing offline tests and the provider-free replay
  preflight passed. No model actor requested additional source-read tools.
- Coordination API elapsed time was 14.04s versus 5.87s, with 26.33s shared
  worker/critic time. These are request durations, not overall delivery speed.
- Preparation started at 17:38:27 UTC; the run completed at 17:46:41 UTC.
  An initial contract label used the earlier KU State snapshot time for
  preparation start; session telemetry corrected it. The hard stop did not change.
  Documentation and verification continued after run completion.
- Coordinator usage through 17:49:52 UTC was 6,051,356 cumulative input tokens,
  including 6,008,448 cached, and 19,999 output tokens. These are sums across
  requests, not unique context size. Subscription cash allocation is
  **unavailable, not zero**, and excluded from the API figures.
  Later publication preparation is also outside those figures.
- This replay deliberately includes three fault/recovery events and one clean
  event. It does not estimate production event frequency. A clean-only workload
  would not get this 75% token reduction.
- Both paths achieved 4/4 correct outcomes. The result demonstrates less model
  work while retaining those outcomes, not a measured increase in accuracy.
- This is local coordination replay, not a production Redis throughput test,
  proof of exactly-once distributed execution or a symbolic compression test.
- A stronger ordinary-runner control, evaluated offline, used the same pinned
  artifact and durable job status to filter all three ineligible events too.
  It was not a live third arm or a fully hardened adapter replacement.

That last control clarifies the engineering advantage: **Semio supplies a
reusable, tested coordination layer instead of leaving message eligibility
to repeated model judgment.** Other correctly engineered host guards can
perform these checks. The measured comparator was agent-managed handovers.

## Inspect the Evidence and Use It

- [Seven sanitized API receipts and aggregate outcomes](receipts.json)
- [Offline cost and token arithmetic verifier](verify.py)
- [Optional Semio adapter](../../adapters/semio.md)
- [Wake runner and host integration](../../examples/semio-coordination/README.md)
- [Compact context packet guide](../../examples/semio-coordination/CONTEXT_PACKETS.md)

```bash
python3 case-studies/semio-coordination-2026-10-20/verify.py
```

The verifier makes no API calls. Public receipts exclude proprietary source,
prompts, provider response IDs, credentials and private logs. They verify
arithmetic; they do not reproduce the private coding assignment.

This is separate from the [cheaper-worker coding comparison](../krystalview-2026-10-20/README.md).
Do not add or multiply their savings percentages. No production service was
changed, restarted or deployed for this test.
