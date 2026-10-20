# A 94.94% cheaper worker. A 24.64% lower measured API total.

**One real coding task, three workflows, the same acceptance checks.**
On 20 October 2026, KU tested a notification-retrieval repair from KrystalView
against a frozen 255-file, 2,450,391-byte source snapshot.

The DeepSeek-worker KLP configuration delivered an accepted fix with the lowest
measured API cost. Its worker cost **$0.0102**, compared with **$0.2016** for the
conventional frontier worker. After independent review and an equal share of
all shared model evaluation, the totals were **$0.2709 versus $0.3595**.

Those are two useful results, not interchangeable percentages:
**94.94% lower worker API cost; 24.64% lower measured API total.**

## What the agents had to fix

Unread notifications were being filtered after pagination. A page could appear
empty even when unread notifications existed further down the list. The task
was to filter before paging, preserve tenant isolation and response formats,
keep ordering stable, and support pagination consistently across the two
retrieval interfaces.

Each worker could edit the same three application files and add focused tests.
The rest of the snapshot remained readable but protected. No production
service, database, customer data or private logs were used.

## The three approaches

| Arm | Implementation | Context and review |
| --- | --- | --- |
| A: conventional frontier | GPT-6.1 Sol, high reasoning | Normal targeted search/read workflow with retained conversation and self-checks; fresh final evaluation |
| B: frontier KLP | GPT-6.1 Sol, high reasoning | Compact task packet, extra reads available, fresh GPT-6 Astra in-loop critic and final evaluation |
| C: DeepSeek KLP | DeepSeek Flash, high reasoning | Same compact-packet approach and tools, same GPT-6 Astra critic and final evaluation |

These are the model identifiers recorded by the endpoints, not a promise of
availability in every agent product. Astra used high reasoning. B's critic was
fresh-context but from the same provider family; C used a different family.

All arms used the same restricted file/search/edit/check controller. OpenAI
used Responses and DeepSeek used Chat Completions. This was not a comparison
of native Codex, Hermes or ZCode clients. A was allowed to search intelligently:
it was **not forced to consume the entire repository**. C, A, B execution order
was fixed before dispatch. Repair rounds were allowed, not manufactured.

## Costs: include the checking

USD, calculated from provider-reported usage and the rates captured on the
test date, including input, cache hits, cache writes and output. These are
usage-based API estimates, not invoice reconciliation.

| API cost component | A: conventional frontier | B: frontier KLP | C: DeepSeek KLP |
| --- | ---: | ---: | ---: |
| Worker, including repairs | $0.201606 | $0.160661 | $0.010199 |
| In-loop critic | $0.000000 | $0.104168 | $0.102805 |
| Shared readiness/final evaluation allocation | $0.157923 | $0.157923 | $0.157923 |
| **Total measured API cost** | **$0.359529** | **$0.422751** | **$0.270926** |
| Formal repair cycles | 1 | 0 | 0 |
| Final frozen checks passed | 15 | 15 | 15 |
| Final worker regression tests passed | 5 | 3 | 4 |

Totals use unrounded receipts. Shared evaluation cost **$0.4737679** across six
inference calls, allocated equally as declared before the test. This includes
A's extra final repair recheck, rather than charging that recheck only to A.
The public call ledger retains its individual cost (`055-shared-final-review`).
A's zero in-loop critic cost does **not** mean its final review was free.

- C's worker cost was **94.94% lower than A** and **93.65% lower than B**.
- C's total measured API cost was **24.64% lower than A** and **35.91% lower than B**.
- B used fewer reported input tokens but cost more than A once review was counted.
- All three runs plus shared evaluation cost **$1.053205606**, against a $50 cap.

There were 55 inference requests and one model-list request. Every inference
receipt is accounted for, including unsuccessful work and the permitted repair.
There were no provider retries, provider failures or missing usage receipts.

### Rates used in the receipts

USD per million tokens; historical test rates, not current pricing advice.

| Model | Uncached input | Cached input | Cache write | Output |
| --- | ---: | ---: | ---: | ---: |
| GPT-6.1 Sol | $2.00 | $0.10 | $2.50 | $10.00 |
| GPT-6 Astra | $10.00 | $1.00 | $12.50 | $50.00 |
| DeepSeek Flash, off-peak | $0.15 | $0.003 | No separately billed writes in these receipts | $0.60 |

The preparation record checked the official
[Sol model page](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[OpenAI model comparison](https://developers.openai.com/api/docs/models/compare?model=gpt-6-astra&model=gpt-6.1-sol)
and [DeepSeek pricing](https://api-docs.deepseek.com/quick_start/pricing/).
DeepSeek ran off-peak. Cache effects are included as observed, not normalized
away; another time, cache state or pricing plan can change the result.

## What the review actually caught

A's first candidate passed the frozen checks and its own tests. The fresh final
review nevertheless identified an existing-input compatibility regression:
an explicitly empty filter value changed which notifications were returned.
An independent SQL probe confirmed the finding against the original behavior.

A then used one permitted repair, added a regression test, passed the unchanged
frozen gate and the additional compatibility probe, and received final PASS.
B and C passed in-loop and final reviews without a formal repair. Worker
self-corrections are still counted: A ran checks four times, B twice, C once.
Different numbers of authored tests are not a quality ranking.

All database checks ran against disposable PostgreSQL in isolated filesystem
and network namespaces. The frozen route probes extracted the relevant
functions; worker tests also imported the actual route modules. This verifies
the bounded retrieval behavior, not production authentication or a live release.

## Full effort and what is not in the dollar table

The receipts include additional reads, tool output, worker self-corrections,
critic calls, repairs and final evaluation. Reported experiment API usage was
869,822 input tokens (757,666 cached) and 32,780 output tokens.
Cache writes were 89,519 tokens, already included in input, not added on top.
Cross-provider token totals are reported usage, not identical units of work.

The Codex coordinator also prepared the harness, inspected evidence and wrote
the results. Through the recorded 12:24:45 UTC checkpoint its telemetry was
**16,770,741 input tokens, including 16,642,560 cached, and 40,269 output**.
These are cumulative billed-input exposures across requests, not unique text.
That shared experiment setup/coordination effort is substantial and is not
being hidden inside the worker-savings headline.

The coordinator used a subscription whose dollar allocation is unavailable,
**not zero**. The table is therefore the full measured experiment API cost,
**not an all-inclusive project cost or subscription savings claim**. Earlier
planning, work after the checkpoint, subsequent integration and publication
preparation are outside these experiment totals. A one-off three-arm experiment
also costs more coordination than doing one accepted task once.

We do not headline speed: execution segments were 204.7s, 184.4s and 81.3s for
A/B/C, but those exclude shared final evaluation and coordinator work.

## What this demonstrates

On this task, a cheaper implementation model plus independent frontier review
delivered a candidate accepted by the experiment's checks at lower measured API cost. Review remained a real
cost and caught a real defect in the conventional arm. Compact context alone
did not guarantee the cheapest result: frontier-only KLP cost more here.

This is one KU-run case, not an independent audit or a universal savings rate.
It compares workflow configurations, not the isolated causal effect of every
KLP component. It does not establish better accuracy across projects, and it
does not attribute these savings to Semio symbols or wake notifications.

## Inspect the arithmetic

[receipts.json](receipts.json) contains an allowlisted, sanitized ledger of
all 55 inference calls, historical rates, aggregates and coordinator telemetry.
It excludes prompts, source, diffs, response bodies, provider response IDs,
host paths, credentials and customer information.

```bash
python3 case-studies/krystalview-2026-10-20/verify.py
```

This offline check recomputes costs and both savings denominators. It makes no
provider calls. The private source and raw evidence are not released, so the
public package supports arithmetic inspection, not independent reproduction
of the proprietary coding task.

### Later integration found another compatibility gap

A fresh integration reviewer found that C's SQL excluded a notification whose
stored read flag was NULL, while the previous implementation treated it as
unread. The schema allowed that value. This is different from the empty request
argument caught in A: the experiment's checks and reviews missed this stored
data case in C.

A new regression reproduced the failure. Integration corrected the SQL
predicate to preserve that behavior, added test-database isolation, and retained
both null regressions. The integrated source is therefore C **plus one bounded
post-experiment correction**, not a byte-identical flawless candidate.

The 94.94% and 24.64% figures remain measurements of the completed experiment,
not the cost of final integration or a production-ready comparison. The later
coordinator work and review are outside those API totals, with subscription
cost allocation unavailable. C's four-test benchmark result remains historical;
the integrated artifact passed 15 frozen checks and six regressions.
No production restart or deployment is claimed.
