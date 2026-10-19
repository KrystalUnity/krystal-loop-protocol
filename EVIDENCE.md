# Measured Benefits and Limits

KLP aims to make bounded agent work more focused and inspectable. This page
summarizes measurements already recorded on **19 October 2026**. Publishing
these results did not run a new benchmark. Normal work uses the selected
packet; a full-context comparison is not a required extra step.

These are KU's own observations, not an independent audit, a production-wide
evaluation or a guarantee of savings. The tables are sanitized aggregates from
retained run receipts and usage records. Private host configuration and raw
execution traces are not published here; the arithmetic is inspectable, but
this page is not a complete benchmark reproduction package.

## 1. One Real Documentation Assignment

**Task:** write the compact-context guide and link it from the Semio example.
The full and compact arms received the same mission, task and source facts.
The full arm used an eight-document reference bundle; the compact arm selected
three relevant documents. Both could request permitted additional source reads
from the same frozen corpus. Neither needed extra reads.

Each arm used an initial worker, an independent critic, one repair worker and
a critic recheck: four model calls per arm, eight total. The accepted compact
guide is published in [commit 5c67ae6](https://github.com/KrystalUnity/krystal-loop-protocol/commit/5c67ae6d2d8d7305f38da6b25958b28e68d6c09d).

| Metric, including repair and recheck | Full | Compact | Reduction |
| --- | ---: | ---: | ---: |
| Worker input tokens | 81,409 | 59,789 | 26.56% |
| Critic input tokens | 23,135 | 22,812 | 1.40% |
| Combined reported input tokens | 104,544 | 82,601 | 20.99% |
| Supplied worker and critic prompt bytes | 330,377 | 181,099 | 45.18% |
| Combined reported output tokens | 14,242 | 10,782 | Not attributed causally |
| Cached input tokens, already included in input | 20,864 | 20,864 | No change |
| Extra worker read commands / bytes | 0 / 0 | 0 / 0 | No change |
| Repair rounds | 1 | 1 | No change |
| Model calls | 4 | 4 | No change |
| Retries / provider failures | 0 / 0 | 0 / 0 | No change |

**Quality evidence:** both arms passed final independent review and mechanical
checks after a factual clarification. The initial critics missed the same
ambiguous count; coordinator source checking caught it, and both repairs and
rechecks are counted above. This demonstrates the checks used on this task,
not statistical quality equivalence or infallible reviewers.

**Limits:** worker and critic tokenizers differ. Their combined counts describe
reported usage, not equal-priced units. Prompt bytes are not tokens. Cached
input is a subset of input, not an additional total. Output and elapsed-time
differences from one pair do not establish general output or speed savings.
Coordinator chat usage, subscription cost and kickoff retrieval embedding
usage were unavailable, not zero. Shared setup and verification effort was
recorded separately; there is no whole-session cost-saving claim.

The experiment itself ran **both** arms: 187,145 reported input tokens and
25,024 output tokens across eight calls. That comparison was not cheaper than
just completing the compact assignment. It is not a routine work requirement.

## 2. Earlier Source-Review Pilot

Three paired source-review cases used one model/settings configuration, with
four obligation classifications per case. All six calls completed. Each mode
classified 12 of 12 obligations correctly, 24 of 24 across both modes.

| Metric, totals across three cases per mode | Full | Compact |
| --- | ---: | ---: |
| Supplied prompt bytes | 194,037 | 87,948 |
| Reported input tokens | 91,017 | 68,601 |
| Cached input tokens, already included in input | 30,720 | 30,720 |
| Output tokens | 863 | 1,013 |

This is **24.63% fewer reported input tokens** and **54.67% fewer prompt bytes**
in a synthetic, source-only pilot. Compact output was higher. It does not
establish authoring quality, general coding productivity, cash savings or
equivalence outside these cases. The earlier results are also recorded in the
[compact packet guide](examples/semio-coordination/CONTEXT_PACKETS.md).

## 3. Event Wake Instead of Repeated Scanning

One controlled pair used isolated local Redis streams, a two-second readiness
delay, and the same predeclared job, candidate and 62,802-byte prompt. Both real
jobs completed and refused another launch after reopening their retained
receipts. The optional bridge is published in
[commit b244990](https://github.com/KrystalUnity/krystal-loop-protocol/commit/b2449906af604eb203944b3332bb163c5c7c58dc).

| Metric | Polling | Event wake |
| --- | ---: | ---: |
| Transport read calls, including the blocking event read | 21 | 3 |
| Prompt bytes | 62,802 | 62,802 |
| Model calls while waiting | 0 | 0 |

The observed read reduction was **85.71%**. It is not an 85.71% reduction in
tokens, money, CPU or total effort. Prompt-byte savings were zero and neither
waiting path called a model. Different reported launch token totals were not
attributed to the wake method. This was one local pair, not a production-scale
performance study. It installed no always-on service.

## 4. Subsequent Coding Use, Without Another Comparison

Compact packets were then used for the critic harness's non-finite timeout
fix, published in [commit c7e90f0](https://github.com/KrystalUnity/krystal-loop-protocol/commit/c7e90f0354f00b7e757b470404f454eb7b0a9593).
One worker and one independent critic completed it with zero extra worker
reads, repairs, retries or provider failures. The integrated public suite
passed 85 tests at that revision.

Reported input was 28,226 worker tokens and 16,232 critic tokens; output was
273 and 3,225 respectively, including reported reasoning. There was no
full-context control, so there is **no savings percentage for this coding
task**. Coordinator usage and monetary cost were unavailable, not zero.

## Structure, Not Magic Symbols

The optional Semio adapter gives notifications explicit message types,
mission/task identities and artifact revisions. For example, a KLP `handover`
maps to outer `propose`, while `finding` and `stop` map to `alert`; the nested
KLP fields preserve the specific meaning. Receivers validate expected
bindings, reject conflicting duplicates and stop on detected retention gaps.

That reduces ambiguity about **which job, which revision and what kind of
message** is being handled. The benefit comes from a shared schema and host
validation, not from symbols forcing a model to reason correctly. Structured
messages can still contain wrong, ambiguous or hostile content. Identity
fields and hashes are not sender authentication or permission to act.

The wake bridge calls a preconfigured, zero-argument host callback; message
text is not passed in as launch instructions. This narrows that injection
path, not all prompt-injection risks. The host must verify local inputs and
permissions and enforce process/transport limits. A retained receipt guards
one local attempt, not exactly-once distributed execution. See the
[adapter boundary](adapters/semio.md) and
[host responsibilities](examples/semio-coordination/README.md).

## Where Further Savings Could Come From

Matching suitable work to lower-cost models, avoiding repeated context,
reusing durable handovers and stopping unproductive repair loops can reduce
waste. These are design opportunities, not additional measured percentages.
Review, packet preparation and missing-context reads also have costs.

During normal bounded work, record per-model input/output and cached usage,
extra reads, reviews, repairs, retries, failures and available billing data.
Record coordinator/setup effort and mark unknowns explicitly. A task without a
comparable baseline can report usage, not a savings claim. No new benchmark
or automatic spending is required to use these practices.

Do not add reductions across these experiments or count worker savings again
on top of the combined total. Do not turn token or transport-read reductions
into a promised subscription discount. KLP remains provider-neutral and the
coordination and compact-packet examples remain optional.
