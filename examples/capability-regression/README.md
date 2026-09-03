# Offline Capability-Regression Fixture

This fixture demonstrates the KLP Core v0.3 product-truth capability gate
without provider egress or production access. It freezes a Mission Contract for
an adaptive-choice capability, establishes accepted baseline evidence, and then
deliberately replaces that behavior with a fixed policy. The ordinary fixture
checks pass, but the Capability Auditor's post-integration probe records a
`capability_regression`, so the run cannot complete until the bounded repair
restores the capability and the exact integrated artifact passes the probe.

The fixture is synthetic and offline. It proves protocol gating, not model
quality or production safety. It does not authorize live capability probes.

## Normal Lifecycle

Run these exact commands from the repository root:

```bash
output="$(mktemp -d)/klp-capability-fixture"
python3 examples/capability-regression/run_fixture.py --out-dir "$output"
python3 -m json.tool "$output/final-receipt.json"
```

The fixture exits `0` after recording the regression, one authorized repair,
and a final `completed` receipt whose affected capability is `preserved`.
Inspect `state-events.jsonl` and `evidence/` in `$output` for the baseline,
failed integration, repaired integration, and direct auditor observations.

## Required Stop Paths

Use a new temporary output directory for each invocation because the fixture
requires an empty output directory.

```bash
output="$(mktemp -d)/klp-capability-zero-repair"
python3 examples/capability-regression/run_fixture.py --out-dir "$output" --repair-round-limit 0
```

This zero-repair invocation exits `3` and produces `budget_exhausted` with the
critical capability marked `degraded`; it never starts an unauthorized extra
repair round.

```bash
output="$(mktemp -d)/klp-capability-inconclusive"
python3 examples/capability-regression/run_fixture.py --out-dir "$output" --probe-mode inconclusive
```

This inconclusive-probe invocation exits `4` and produces
`capability_unproven`. Inconclusive capability evidence cannot be converted
into `completed` by passing task checks or criticism.

```bash
output="$(mktemp -d)/klp-capability-mismatch"
python3 examples/capability-regression/run_fixture.py --out-dir "$output" --omit-capability-declaration
```

This mission-mismatch invocation exits `5` and produces `mission_mismatch`
before worker execution because a changed surface triggers an undeclared
critical capability.

The fixture returns `2` only for an internal fixture error, such as an invalid
or non-empty output destination. Any other exit code is unexpected and should
be investigated rather than interpreted as capability proof.

## What The Fixture Demonstrates

- The Mission Contract is immutable for the run, and a Task Contract binds its
  `mission_id`, `mission_revision`, and `mission_hash`.
- The Capability Auditor records accepted-baseline and post-integration
  observations against exact artifact revisions with declared controls.
- An ordinary green check or a critic verdict cannot override a `degraded` or
  `unproven` critical capability.
- A missing declaration for a triggered capability is `mission_mismatch`.
- Scheduled monitoring may supplement this proof in a deployed system, but it
  never replaces the required post-integration capability gate.

For the normative rules, read the [KLP Core protocol](../../PROTOCOL.md). For
the earlier lifecycle mechanics, use the
[fail-review-repair fixture](../fail-review-repair/README.md).
