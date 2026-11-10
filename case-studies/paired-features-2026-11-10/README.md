# Paired Features: Semio Integrates With 43% Fewer Model Calls, and Two Low-Cost Workers Beat the Frontier Model Alone

Thirty pairs of features whose reference patches conflict when merged. Two
low-cost workers each built one feature under KLP, and the Semiotic Protocol
(Semio) carried the handover that brought both into one tree. The result
passed both features' hidden tests on 28 of 30 pairs for $0.103 a pair. The
frontier model building both features alone passed 22 of 30 for $0.196 a pair.
Run on 10 November 2026: 120 runs, 1,272 model calls.

## Two workers with Semio against one frontier model

| | Pairs passing both hidden test sets | Cost per pair | Cost per passing pair |
| --- | ---: | ---: | ---: |
| Frontier model alone, both features (`gpt-6.1-sol`, high reasoning) | 22 of 30 | $0.196 | $0.267 |
| **Two `deepseek-flash` workers under KLP Standard, integrated through Semio** | **28 of 30** | **$0.103** | **$0.110** |

Six more pairs delivered, at 47% less per pair and 59% less per passing pair.
The KLP figure includes everything: building both features, their independent
review and repair, and the integration.

## What Semio changed in the integration

Both arms below start from the same two finished features, the same workspaces
and the same worker sessions. Only the coordination differs.

| Integration of 30 conflicting pairs | Agent-managed chat | Semio | Difference |
| --- | ---: | ---: | ---: |
| Pairs passing both hidden test sets | 28 | 28 | same |
| Model calls | 581 | 333 | 43% fewer |
| Worker sessions woken | 60 | 28 | 53% fewer |
| Input tokens | 31.2 million | 20.9 million | 33% fewer |
| Integration cost | $0.567 | $0.222 | 61% lower |
| Median time per pair | 63 s | 44 s | 30% faster |
| Pairs settled with no model call | 0 | 2 | |

- **Agent-managed chat.** Both workers are woken and told a teammate has
  finished another feature. Each can read the other's patch. They agree in
  free-text messages who integrates, and one of them does it. Eighty messages
  went back and forth, and both sessions spent model calls on every pair.
- **Semio.** Each worker's finished feature is one typed handover naming the
  exact artifact. Software receives both, tries the merge and runs the tests.
  Two pairs merged and passed with no model involved. For the other 28 the
  software addressed one handover to one worker, with the peer's exact
  artifact and the conflicting files. The other worker was never woken.
- **Plain git merge** of the two patches passed 2 of 30. The other 28
  conflicted, which is what makes these pairs a coordination test.

The messages ran through the repository's public
[Semio adapter](../../examples/semio-coordination/README.md): identity-bound
envelopes, duplicate suppression and one inbox per agent.

## Method

- **Pairs.** From the public [CooperBench](https://github.com/cooperbench/CooperBench)
  dataset at revision `63b9d44d`, the feature pairs in Click, Jinja and
  dirty-equals that its conflict report marks as conflicting. Of those, 162
  have both features individually passing their hidden tests in run 3 of the
  [feature benchmark](../feature-benchmark-2026-11-10/README.md). Thirty were
  drawn with a fixed seed, spread across the seven base commits.
- **Starting point.** For the merge, chat and Semio arms, each feature is the
  finished run 3 candidate: `deepseek-flash` worker, `gpt-6.1-sol` critic,
  bounded repair. Its cost is in [`feature-costs.json`](feature-costs.json)
  and is counted in the cost per pair.
- **Integration.** The integrating worker continues its own session in its own
  workspace and receives the peer's patch and task statement as files. In both
  arms the runner then executes both features' existing tests on the
  integrated tree and allows one bounded repair if they fail.
- **Frontier alone.** `gpt-6.1-sol` at high reasoning effort gets both task
  statements in a fresh checkout and builds both features in one session.
- **Grading.** The final tree is applied to a pristine checkout and graded
  separately against each feature's hidden tests. A pair passes when both do.
  Every feature's hidden tests were checked beforehand against the dataset's
  all-features reference patch, so they hold with other features present.
- **Cost.** From provider-reported token usage at the rates in
  [`prices.json`](prices.json). The integration and the features ran in
  DeepSeek's off-peak hours; each call carries the tier it was billed at.
- **Code.** [`bench/pairs.py`](../../bench/pairs.py) at runner revision `7bd3af7`
  plus this change.

## Check it and run it

```bash
python3 case-studies/paired-features-2026-11-10/verify.py
```

The checker reprices every call in [`ledger.jsonl`](ledger.jsonl), sums the
calls for each run in [`results.json`](results.json) and rebuilds the table in
[`report.json`](report.json). [`pairs.json`](pairs.json) lists the 30 pairs.

To run it yourself, finish the feature benchmark's `worker-3` and `klp-3` arms
first, then:

```bash
python3 -m bench.pairs select --work ~/klp-bench --pairs 30
python3 -m bench.pairs run --work ~/klp-bench --arms merge,chat,semio,solo --cap 16
```

The chat and Semio arms together cost under $1; the frontier arm about $6.
