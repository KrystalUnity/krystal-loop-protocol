#!/usr/bin/env python3
"""Recompute the paired-feature benchmark from its receipts. Offline, standard library only.

    python3 case-studies/paired-features-2026-11-10/verify.py

Each call's cost is recomputed from its token usage at the recorded price for the hour it ran in, each run's
cost is the sum of its calls, and the report's rows are rebuilt from the per-run results. The cost of building
and reviewing the two features of a pair comes from feature-costs.json, which lists what each feature cost in
the feature benchmark's run 3.
"""
import json
import sys
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent


def price(usage, rates):
    fresh = usage["input"] - usage["cached"] - usage["write"]
    return (D(fresh) * D(str(rates["input"])) + D(usage["cached"]) * D(str(rates["cached"]))
            + D(usage["write"]) * D(str(rates["write"])) + D(usage["output"]) * D(str(rates["output"]))) / D(1_000_000)


def main():
    prices = json.loads((HERE / "prices.json").read_text())["usd_per_million_tokens"]
    calls = [json.loads(line) for line in (HERE / "ledger.jsonl").read_text().splitlines()]
    results = json.loads((HERE / "results.json").read_text())
    report = json.loads((HERE / "report.json").read_text())
    pairs = {p["id"]: p for p in json.loads((HERE / "pairs.json").read_text())["pairs"]}
    built = {task: sum(D(v) for v in arms.values()) for task, arms in json.loads((HERE / "feature-costs.json").read_text()).items()}
    problems, by_scope, count = [], {}, {}
    for call in calls:
        if call["status"] != "completed":
            continue
        rates = prices[call["model"]]
        expected = price(call["usage"], rates["off_peak"] if call.get("tier") == "off_peak" else rates)
        if expected != D(call["usd"]):
            problems.append(f"call {call['id']}: recorded {call['usd']}, recomputed {expected}")
        by_scope[call["scope"]] = by_scope.get(call["scope"], D(0)) + expected
    for call in calls:
        count[call["scope"]] = count.get(call["scope"], 0) + 1
    arms = {}
    for run in results:
        scope = f"pair-{run['arm']}/{run['pair']}"
        if by_scope.get(scope, D(0)) != D(run["usd"]) or count.get(scope, 0) != run["model_calls"]:
            problems.append(f"run {scope}: recorded {run['usd']} / {run['model_calls']} calls, ledger has "
                            f"{by_scope.get(scope, D(0))} / {count.get(scope, 0)}")
        arms.setdefault(run["arm"], []).append(run)
    print(f"{report['pairs_compared']} pairs, {len(results)} runs, {len(calls)} model calls\n")
    print(f"{'':74s}{'solved':>8s}{'calls':>7s}{'woken':>7s}{'integration':>13s}{'per pair':>10s}")
    for label, row in report["arms"].items():
        runs = arms[row["arm"]]
        own = sum((D(r["usd"]) for r in runs), D(0))
        features = D(0) if row["arm"] == "solo" else sum((built[pairs[r["pair"]]["a"]] + built[pairs[r["pair"]]["b"]] for r in runs), D(0))
        got = (sum(bool(r["solved"]) for r in runs), sum(r["model_calls"] for r in runs),
               sum(r.get("sessions_woken") or 0 for r in runs), own, own + features)
        said = (row["solved"], row["model_calls"], row["sessions_woken"], D(row["integration_usd"]), D(row["usd"]))
        if got != said:
            problems.append(f"{label}: report {said}, receipts {got}")
        print(f"{label[:72]:74s}{got[0]:>5d}/{len(runs):<3d}{got[1]:>6d}{got[2]:>7d}{float(own):>13.4f}{float(got[4] / len(runs)):>10.4f}")
    print()
    for problem in problems:
        print("MISMATCH:", problem)
    print("All figures recompute from the receipts." if not problems else f"{len(problems)} mismatch(es).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
