# Verify KLP Yourself

Run the public examples, inspect their evidence and check the savings arithmetic.
Everything on this page uses source already in this repository. No API keys,
model subscription or access to KU infrastructure is needed.

## Get the Source

Use Python 3.12 or newer, Git, and a POSIX shell (Linux, macOS or WSL).
No pip packages are required. Clone once, then the checks below need no external
network access. The capability demo temporarily binds a localhost port for its
fake critic; an environment that forbids loopback sockets cannot run that demo.

```bash
git clone https://github.com/KrystalUnity/krystal-loop-protocol.git
cd krystal-loop-protocol
git rev-parse HEAD
```

Keep that revision with any results you share. If you already have a checkout,
start there rather than cloning over it. Use a clean checkout for a reproducible
report, or retain the exact diff as well as the revision.

## 1. See a Regression Caught and Repaired

The public miniature program chooses a different action for different inputs.
The scripted worker replaces it with a constant response. Ordinary tests check
the response shape and allowed vocabulary, so they still pass. The capability
probe checks the promised behavior and catches what those tests missed.

Run from the repository root:

```bash
output="$(mktemp -d)/klp-demo"
env -i PATH="$PATH" LANG=C.UTF-8 python3 examples/capability-regression/run_fixture.py --out-dir "$output" &&
python3 -m json.tool "$output/final-receipt.json"
```

The expected process exit is `0`. The final receipt should say `completed`,
with one repair and capability results `before: passed`, `intermediate: failed`,
`after: passed`, `disposition: preserved`. This is not completion of the broken
candidate: inspect the evidence to see the failed gate before repair.

| Evidence inside the generated directory | What to check |
| --- | --- |
| `workspace/chooser.py` and its Git history | Public baseline, deliberate regression and repair. |
| `evidence/worker-check.txt` | Ordinary task tests passed on the broken worker artifact. |
| `evidence/capability-baseline.json` | Accepted baseline behavior and exact artifact identity. |
| `evidence/capability-after-integration-1.json` | The first integrated artifact failed the capability probe. |
| `evidence/capability-after-integration-2.json` | The repaired integrated artifact passed. |
| `state-events.jsonl` | `capability_regression` occurred before `completed`. |
| `final-receipt.json` | Outcome, limitations, evidence references and measured local elapsed time. |

The worker is scripted and the loopback fake critic returns predetermined
verdicts. This executes real Git changes, checks and protocol gates, not real
model reasoning. It proves the gate catches this regression; it does not measure
model quality or reproduce API cost savings. All generated files stay in the
temporary output directory, which remains available for inspection.

Run the [full capability tests](examples/capability-regression/tests/test_fixture.py)
to verify missing-proof, missing-declaration and exhausted-budget stops too:

```bash
env -i PATH="$PATH" LANG=C.UTF-8 python3 -m unittest discover -s examples/capability-regression/tests -v
```

The suite expects those stop paths and reports `OK` when their assertions pass.
That does not turn a stopped fixture into a completed run. For individual
scenarios and their nonzero exit codes, see the [fixture guide](examples/capability-regression/README.md).

## 2. Check Semio's Coordination Behavior

```bash
env -i PATH="$PATH" LANG=C.UTF-8 python3 -m unittest discover -s examples/semio-coordination/tests -v
```

These tests exercise the public adapter and wake runner with a fake transport,
including duplicates, stale identities and restart/claim handling. They need
neither Redis nor a model. Inspect [the tests](examples/semio-coordination/tests)
to see exactly what is asserted. This verifies the coordination mechanisms;
it does not independently reproduce the four-scenario paid-model experiment
or predict the frequency of duplicate messages in your workload.

## 3. Recalculate the Published Savings

```bash
env -i PATH="$PATH" LANG=C.UTF-8 python3 case-studies/krystalview-2026-10-20/verify.py
env -i PATH="$PATH" LANG=C.UTF-8 python3 case-studies/semio-coordination-2026-10-20/verify.py
```

Run Python normally, not with `-O`, which disables these verifiers' assertions.
The first checks 55 recorded calls and prints **94.94% lower worker API cost**
and **24.64% lower API cost including equal shared evaluation**. The second checks
seven recorded calls and prints **75.00% fewer coordination input tokens**, four
calls versus one, and the separate cache-equalized cost calculation.

The scripts recompute costs and totals from the included sanitized usage records
and recorded rates. They do not call a provider or authenticate those records
against provider billing. Outcome fields are retained experiment summaries,
not freshly executed quality checks. This is arithmetic verification,
not a replay of the private coding task.

Read the [coding case study](case-studies/krystalview-2026-10-20/README.md) and
[coordination case study](case-studies/semio-coordination-2026-10-20/README.md)
for the methods, quality evidence and cost boundaries. Do not add the percentages:
worker pricing and avoided coordination calls are different effects.

## Share or Extend the Evidence

For a reproduction report, include the commit/diff, Python and Git versions,
command, exit code, relevant evidence and elapsed time. A failure report is useful
too. Do not include credentials, customer data or unrelated machine logs.

A fully repeatable **model-cost comparison** is a separate next step, not one
of the offline demos above. It needs a public task repository or frozen fixture,
the same start state and acceptance tests for every arm, published prompts and
runner configuration, declared budgets, and complete usage for reads, reviews,
repairs and failures. Record coordinator cost separately when unavailable.
To attribute savings to Semio, hold task, models and evidence fixed and vary the
coordination path rather than changing the worker model at the same time.

The existing private KrystalView source is not part of this distribution. A
small standalone public task could live here first and become a separate repo
if it needs its own release cycle. No paid benchmark is launched by these commands.
