# Offline Fail-Review-Repair Fixture

This fixture proves one complete KLP Core v0.2 lifecycle without an external
provider, paid inference, or a live project. It uses a temporary Git repository,
a scripted worker defect, the real sealed-packet critic harness, and a loopback
fake `/chat/completions` provider.

## Run

Prerequisites are Python 3.11 or later and Git.

```bash
output="$(mktemp -d)/klp-fixture"
python3 examples/fail-review-repair/run_fixture.py --out-dir "$output"
python3 -m json.tool "$output/final-receipt.json"
```

The output directory must be new or empty. No environment credentials are read.
The only HTTP request is to a temporary server bound to `127.0.0.1`.

## What It Proves

The successful path records:

1. a hashed root contract with declared delegation and measured limits;
2. an exact worker Git revision with an intentional lower-bound defect;
3. a failed deterministic check before criticism;
4. a critic verdict bound to that exact revision;
5. one real finding confirmed and one false finding refuted using the same
   direct test evidence;
6. one authorized repair within the frozen contract;
7. passing repair and integration checks;
8. an append-only, hash-chained `state-events.jsonl` ledger;
9. a complete receipt with claims, evidence, measured budget, limitations,
   unresolved findings, and human decisions still required.

The completed synthetic run has no consequential action pending, so
`human_decisions_required` is empty. This demonstrates that KLP does not require
a human approval click for each normal loop round.

## Stop Proof

Set the repair budget to zero to prove the loop stops after the confirmed
finding rather than applying an unauthorized repair:

```bash
output="$(mktemp -d)/klp-fixture-stop"
python3 examples/fail-review-repair/run_fixture.py \
  --out-dir "$output" \
  --repair-round-limit 0
test "$?" -eq 3
```

That run writes a `budget_exhausted` final receipt, preserves the unresolved
finding, and identifies the decision required to continue.

## Limits

The worker and critic responses are scripted. The fixture proves record,
revision, adjudication, budget, repair, and integration mechanics. It does not
measure whether a real model writes good code or whether a project is safe to
deploy.

Run the regression tests with:

```bash
python3 examples/fail-review-repair/tests/test_fixture.py -v
```
