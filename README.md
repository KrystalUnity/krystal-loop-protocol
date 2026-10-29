# Krystal Loop Protocol

![Krystal Loop Protocol](assets/krystal-loop-protocol-banner.jpg)

Use fast AI agents for bounded work. Freeze the product promise and use direct
evidence to keep the project coherent, working, and under your control.

AI coding agents can produce a lot of code quickly. The harder problem begins
after the first impressive demo: agents lose context, overlap each other's
changes, trust confident summaries, reopen solved problems, and quietly break
features that worked yesterday.

Krystal Loop Protocol (KLP) is a practical operating pattern for continuing to
build with multiple AI agents without handing them control of the project.

## Start Here

**Ordinary coding task? Start with Standard.** You need Git, one short
[task record](examples/standard-task.md), a worker and a separate reviewer.

1. **Give it a clear job.** Record what should change, what must keep working,
   the edit boundary, checks and a finite budget.
2. **Build and check.** The worker implements the change and runs the relevant
   checks. A skipped check is not a pass.
3. **Get a second pair of eyes.** A fresh, read-only critic reviews the actual
   result and confirms Standard fits. Resolve findings with evidence, not votes.
4. **Finish or stop.** Repair confirmed blockers within budget, verify the
   integrated result and record the outcome. Advisory suggestions do not keep
   the loop running. Shipping still needs its own authority and release checks.

No compulsory message bus, per-step ledger or custom stamping scripts.
[Working solo? Here is the role setup](examples/solo-operator.md).

**Changing saves, security, money or a protected core capability?** Use the
[Critical path](EXECUTION_PROFILES.md#critical-preserve-the-existing-core-gate).
It requires proof the product still does its main job before and after the change.
Read [profile selection](EXECUTION_PROFILES.md#select-before-editing) first;
existing Critical runs cannot be downgraded to bypass their checks.

## Try the Demo

**Watch KLP catch a broken product even when ordinary tests pass.** From a
checkout, with Python 3.12+, Git and a POSIX shell:

```bash
output="$(mktemp -d)/klp-demo"
python3 examples/capability-regression/run_fixture.py --out-dir "$output" &&
python3 -m json.tool "$output/final-receipt.json"
```

The demo makes a tiny program stop responding correctly to different inputs.
Its ordinary checks stay green. The capability gate catches the regression,
blocks acceptance, then verifies one repair. Inspect the receipt's
`capability_report`: `before: passed`, `intermediate: failed`, `after: passed`.

This is executable, public source with a scripted worker and loopback fake
critic. No API keys, paid calls or production access. It demonstrates the gate,
not model intelligence. It binds a temporary localhost port and keeps evidence
in the generated directory; a restricted environment may need loopback permission.

**[Verify it yourself](VERIFY.md):** inspect the demo evidence, run Semio's
offline checks, and recalculate the published savings from the included receipts.

**Try it with your own coding agent:** the
[KLP Public Coding Challenge](https://github.com/KrystalUnity/klp-public-challenge)
provides an original bug, fixed checks and a one-command offline demo. Compare
conventional coding, same-model KLP and cheaper-worker KLP on the same task,
recording reviews, retries and unknown costs. The demo needs Linux/WSL and Python
3.12+, but no API key. Live model runs use your own harness and declared budget;
this public task does not replay the private KrystalView experiment.

## What You Gain

- **Less repeated explanation.** Give each agent the material needed for its
  assignment, not the whole project history. Compact packets retain the full
  mission, task requirements and required evidence.
- **Use your strongest model where it matters.** Delegate suitable bounded
  work to a lower-cost capable model while keeping planning and independent
  review. This is a model-choice option, not a promised reduction in your bill.
- **Clearer handovers.** Explicit task IDs, revisions and message types help
  agents distinguish a status update, a question and a finding. The optional
  Semio adapter checks those bindings; a message is not permission to act.
- **Less checking for updates.** An optional wake bridge can notify a
  preconfigured job when its expected event arrives, instead of repeatedly
  scanning for it. Duplicate, stale and already-attempted notifications can
  be handled before they consume another model turn.
- **A stopping point.** Shared effort budgets and repair limits keep the
  assignment bounded. Tests, independent review and capability evidence still
  matter; a smaller prompt is not an excuse to skip them.

### What We Have Measured

**Semio cut coordination input tokens by 75%, with every scenario handled
correctly.** In a four-scenario comparison against agent-managed handovers,
the optional Semio adapter reduced coordination model calls **from four to
one** and input tokens **from 5,325 to 1,331**. Both paths achieved **4/4 correct
outcomes**. The saving came from handling duplicate, stale and already-attempted
work before it reached the model, not from dropping the coding checks or review.
See the [Semio coordination case study and seven sanitized receipts](case-studies/semio-coordination-2026-10-20/README.md).

On a real coding repair from a **255-file KrystalView snapshot**, a DeepSeek
worker with frontier review cost **94.94% less for the worker** than the
conventional frontier worker. Including critics and an equal share of all
shared model evaluation, **total measured API cost was 24.64% lower**:
**$0.2709 versus $0.3595**. All final candidates passed the same 15 checks;
the conventional arm needed one review-driven repair, which is counted.
Coordinator subscription cost is unavailable and is not included as zero.
Later integration review found and corrected one additional C compatibility
gap; that subsequent work is outside the experiment's cost figures.
See the [three-way coding case study and sanitized receipts](case-studies/krystalview-2026-10-20/README.md).

One real documentation assignment used **20.99% fewer reported worker-plus-critic
input tokens** with compact packets, including repairs and review rechecks.
Both versions passed final review after one repair each. Separately, one local
wake comparison reduced transport reads from **21 to 3 (85.71%)**, with no
observed prompt-byte savings.

These are small, task-specific observations, not a guaranteed cost or quality
improvement. The percentages measure different things and must not be added
together. See [Measured benefits and limits](EVIDENCE.md) for the totals,
methods, unavailable costs and further results already recorded.

## What This Prevents

| Common agent failure | KLP response |
| --- | --- |
| Two agents edit the same shared file. | Give each worker an explicit file and action boundary. |
| A worker says its own work is complete. | Separate factual handover from independent acceptance. |
| A critic reviews an outdated build. | Bind every verdict to an exact artifact revision. |
| A critic confidently reports a false problem. | Confirm or refute every finding with direct evidence. |
| Agents keep looping without improvement. | Stop on repeated findings, exhausted budgets, or a plateau. |
| New tooling creates more work than the requested change. | Reassess whether the tooling is necessary; simplify the approach inside delegation. |
| Unit changes pass but break when combined. | Review integration as a new artifact. |
| A test or agent message is treated as permission to deploy. | Keep live actions behind an explicit human decision. |

## Start With One Prompt

Give this to the lead agent before a multi-agent build:

```text
Work under Krystal Loop Protocol.
Read EXECUTION_PROFILES.md, select the profile and record why before editing.
For Standard, follow its complete checklist using examples/standard-task.md:
one record, bounded work, relevant checks, independent review and integration.
For Critical, follow PROTOCOL.md in full. Do not downgrade existing gates.
Follow AI_AGENT_INTEGRATION.md and SAFETY_AND_LIMITS.md for context, isolation,
evidence and authority. Reuse checks; do not invent extra process machinery.
Finish when the required proof is met. If proof is missing, preserve the work,
state the exact blocker and smallest next action, then stop affected work.
Keep routine shipping behind EXECUTION_PROFILES.md's routine-release-gate.
No profile grants deployment, spending or publication authority.
Runnable offline references: examples/capability-regression/README.md and
examples/fail-review-repair/README.md. See VERIFY.md for what each proves.
```

KLP does not require a special model, database, vector store, or message bus.
You can start with Git and Markdown files, then add durable coordination when
the project needs it.

## Run a Worker and Critic

The included examples demonstrate one complete bounded path:

```text
DeepSeek Flash worker
  -> exact revision and deterministic checks
  -> controller-redacted, sealed review packet
  -> different-family read-only critic
  -> evidence-backed finding dispositions
  -> bounded repair or integration
```

Start with the [DeepSeek Codex worker](examples/deepseek-codex-worker/README.md),
then use the
[OpenAI-compatible critic harness](examples/openai-compatible-critic/README.md).
The worker launcher uses an isolated Codex profile and a reviewed assignment.
The critic makes one request, validates its structured verdict locally, and
cannot edit or authorize any action. The examples do not automatically connect
worker output to critic input; the controller must inspect and redact the
review packet first.

## Run the Offline Lifecycle Proof

The [fail-review-repair fixture](examples/fail-review-repair/README.md) proves a
complete bounded lifecycle without provider egress or model spend:

```bash
output="$(mktemp -d)/klp-fixture"
python3 examples/fail-review-repair/run_fixture.py --out-dir "$output"
python3 -m json.tool "$output/final-receipt.json"
```

It creates a temporary Git project, records a deliberately incomplete worker
revision, captures a failed check, runs the sealed critic harness against a
loopback fake provider, confirms one real finding, refutes one false finding,
applies one authorized repair, and re-checks the integrated artifact. A second
test proves a zero-round repair budget stops instead of overrunning authority.

The [capability-regression fixture](examples/capability-regression/README.md)
proves the v0.3 product-truth gate. It establishes an accepted baseline,
deliberately regresses an adaptive capability while task checks pass, blocks
completion, repairs within the declared limit, and proves the repaired
integrated artifact. Both lifecycle fixtures are offline protocol examples:
neither certifies production safety.

## Let Software Run the Repetitive Checks

An AI reviewer should judge the evidence, not spend turn after turn launching
the same tests. The optional [capability audit runner](examples/capability-audit/README.md)
runs approved checks against frozen before-and-after versions, isolates each
execution, and prepares a compact evidence packet for independent review.

The collector makes no model calls. It retains failed checks and incomplete
evidence instead of converting them into a green result. Use it when a task
already needs a capability audit; ordinary Standard work stays lightweight.

The runner has been exercised on a real, asset-heavy game repository: 42 probe
executions including preflight and a bounded correction. See the
[validation note](examples/capability-audit/VALIDATION.md) for results and full-effort
limits. This demonstrates collection and review, not a new measured cost-saving
percentage. Linux, Python, Git and Bubblewrap are required.

## Read Next

- [Standard and Critical execution profiles](EXECUTION_PROFILES.md)
- [Compact Standard task record](examples/standard-task.md)
- [Solo-operator role example](examples/solo-operator.md)
- [Public demo and evidence verification](VERIFY.md)
- [Public coding challenge for your own agents](https://github.com/KrystalUnity/klp-public-challenge)
- [KLP Core protocol for Critical work](PROTOCOL.md)
- [Recovering missing capability proof](PROTOCOL.md#recovering-missing-capability-proof)
- [Instructions for AI agents and orchestrators](AI_AGENT_INTEGRATION.md)
- [Optional runtime profiles](RUNTIME_PROFILES.md)
- [Safety and limits](SAFETY_AND_LIMITS.md)
- [DeepSeek Codex worker example](examples/deepseek-codex-worker/README.md)
- [OpenAI-compatible critic example](examples/openai-compatible-critic/README.md)
- [Offline fail-review-repair fixture](examples/fail-review-repair/README.md)
- [Offline capability-regression fixture](examples/capability-regression/README.md)
- [Optional deterministic capability audit runner](examples/capability-audit/README.md)
- [Hermes Kanban adapter example](adapters/hermes-kanban.md)
- [Optional Semio agent-coordination adapter](adapters/semio.md)
- [Compact context packet guide](examples/semio-coordination/CONTEXT_PACKETS.md)
- [Measured benefits and limits](EVIDENCE.md)

## What KLP Is Not

KLP is not an autonomous software factory, deployment platform, model router,
or claim that tests prove a product has no defects. It is a portable way to
bound multi-agent work, retain useful evidence, and make uncertainty visible.

**KLP checks how software changes earn acceptance; runtime controls govern what
that software can do after deployment.** Release verification is a checkpoint,
not continuous runtime enforcement. Runtime governance is a separate layer;
using KLP does not install or integrate a runtime enforcement product.

KLP is inspired by public builder/critic systems such as the
[Gauntlet Loop](https://somethingbig.ai/gauntlet-loop). It does not claim to
invent multi-agent coding, independent review, or automated testing. Its focus
is what happens after the demo, when a real project must remain understandable
and working across many changes.

## Project Status

The current package revision is **v0.3.3-draft**, a provisional public profile.
It adds critic confirmation of Standard eligibility, a separate routine-release
gate and approved project economy policy, with behavior-based trigger guidance.
Critical retains `klp-core/v0.3` unchanged.
Standard is documented as `klp-standard/v0.1`; existing validators and adapters
do not automatically accept it. No existing record is silently migrated.

This repository includes a
portable worker launcher, a sealed-packet critic harness, local fake-provider
tests, Mission Contract examples, and reproducible offline lifecycle fixtures.
The fixtures prove protocol mechanics and capability-gate behavior; they do not
certify model quality, production safety, or a particular agent framework.

## License

Krystal Loop Protocol uses split licensing:

- software, scripts, schemas, configuration examples, and tests are licensed
  under [Apache License 2.0](LICENSE-APACHE-2.0) (`Apache-2.0`);
- protocol and documentation text are licensed under
  [Creative Commons Attribution 4.0](LICENSE-CC-BY-4.0) (`CC-BY-4.0`).

See the [licensing map](LICENSE) for the file-level boundary.
