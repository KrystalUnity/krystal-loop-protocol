# Verify KLP Yourself

Run the public examples, inspect their evidence, recompute every published
figure and rerun the benchmark. Sections 1 to 5 use source already in this
repository. No API keys, model subscription or access to KU infrastructure is
needed for them. Section 6 reruns the benchmark with your own keys.

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
to see exactly what is asserted.

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

The scripts recompute costs and totals from the included usage records and
recorded rates. This is arithmetic verification, not a replay of the private
coding task. Read the [coding case study](case-studies/krystalview-2026-10-20/README.md)
and [coordination case study](case-studies/semio-coordination-2026-10-20/README.md)
for the methods.

## 4. Check the Standard Runner

```bash
env -i PATH="$PATH" LANG=C.UTF-8 python3 tests/test_standard_runner.py -v
```

Scripted models drive the real loop inside the real sandbox: a confirmed
finding is repaired and reviewed again, a refuted finding starts no repair, a
repair that breaks the checks is discarded, the cost limit stops the run, and
the critic sees the real change even when the worker tampers with git. The
sandboxed cases need bubblewrap with user namespaces and skip without it.

## 5. Recompute the Feature Benchmark

```bash
env -i PATH="$PATH" LANG=C.UTF-8 python3 case-studies/feature-benchmark-2026-11-10/verify.py
```

The checker reprices every recorded model call from its token usage, sums the
calls for each run, and rebuilds the published table from the per-run results.
It prints the table and `All figures recompute from the receipts.`

## 6. Rerun the Feature Benchmark

```bash
python3 -m bench.features prepare --work ~/klp-bench
python3 -m bench.features run --work ~/klp-bench --cap 25
```

`prepare` builds the task environments and validates all 66 tasks against their
reference patches and hidden tests without a model call. `run` needs
`DEEPSEEK_API_KEY` and `OPENAI_API_KEY`, or your own models in
[`bench/models.json`](bench/models.json), and stops at the spend cap you set.
See the [benchmark guide](bench/README.md).

## Share or Extend the Evidence

For a reproduction report, include the commit, Python and Git versions, the
command, exit code, `report.json` and elapsed time. A failure report is useful
too. Leave out credentials, customer data and unrelated machine logs.

To measure your own models, edit [`bench/models.json`](bench/models.json) and
rerun. To attribute a saving to Semio, hold the task, models and evidence fixed
and vary only the coordination path.

The [KLP Public Coding Challenge](https://github.com/KrystalUnity/klp-public-challenge)
is a single original task with fixed checks, useful for a first `klp run`.
