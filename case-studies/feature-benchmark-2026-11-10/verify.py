#!/usr/bin/env python3
"""Recompute every published figure of the feature benchmark from its receipts. Offline, standard library only.

    python3 case-studies/feature-benchmark-2026-11-10/verify.py

Checks, in order:
1. each model call's cost equals its reported token usage times the recorded price for the hour it ran in;
2. each run's cost equals the sum of its calls;
3. the report's solve counts and totals equal what the per-run results add up to.

A review arm works on candidates built by another arm (`candidates_from` in the report), so its cost is its
own critic and repair calls plus the worker calls that built the candidate. A critic reached through a
subscription CLI is recorded with `metered: false` and no metered cost.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
RATES = ("input", "cached", "write", "output")


def price(usage: dict, rates: dict) -> D:
    r = {k: D(str(rates[k])) for k in RATES}
    fresh = usage["input"] - usage["cached"] - usage["write"]
    return (D(fresh) * r["input"] + D(usage["cached"]) * r["cached"] + D(usage["write"]) * r["write"]
            + D(usage["output"]) * r["output"]) / D(1_000_000)


def main() -> int:
    prices = json.loads((HERE / "prices.json").read_text())["usd_per_million_tokens"]
    calls = [json.loads(line) for line in (HERE / "ledger.jsonl").read_text().splitlines()]
    results = json.loads((HERE / "results.json").read_text())
    report = json.loads((HERE / "report.json").read_text())
    problems = []

    by_scope: dict[str, D] = {}
    unmetered: dict[str, int] = {}
    for call in calls:
        if call["status"] != "completed":
            continue
        arm = call["scope"].split("/")[0]
        if call.get("metered") is False:
            expected = D(0)
            unmetered[arm] = unmetered.get(arm, 0) + 1
        else:
            rates = prices[call["model"]]
            expected = price(call["usage"], rates["off_peak"] if call.get("tier") == "off_peak" else rates)
        if expected != D(call["usd"]):
            problems.append(f"call {call['id']}: recorded {call['usd']}, recomputed {expected}")
        by_scope[call["scope"]] = by_scope.get(call["scope"], D(0)) + expected

    arms: dict[str, dict] = {}
    for run in results:
        scope = f"{run['arm']}/{run['task']}"
        if by_scope.get(scope, D(0)) != D(run["usd"]):
            problems.append(f"run {scope}: recorded {run['usd']}, calls sum to {by_scope.get(scope, D(0))}")
        arms.setdefault(run["arm"], {})[run["task"]] = run

    common = sorted(set.intersection(*[set(tasks) for tasks in arms.values()]))
    print(f"{len(common)} tasks, {len(results)} runs, {len(calls)} model calls\n")
    print(f"{'':78s}{'solved':>8s}{'total USD':>11s}{'per task':>10s}{'per solved':>12s}")
    for label, published in report["arms"].items():
        arm = published["arm"]
        if arm == "klp:first-candidate":  # the single-pass KLP arm's worker, graded before review
            rows = [arms["klp"][task] for task in common]
            total = sum((D(r["effort"].get("worker", {}).get("usd", "0")) for r in rows), D(0))
            solved = sum(bool(r["first_candidate_solved"]) for r in rows)
        else:
            rows = [arms[arm][task] for task in common]
            built = arms.get(published.get("candidates_from") or "", {})
            total = sum((D(r["usd"]) + (D(built[r["task"]]["usd"]) if r["task"] in built else D(0)) for r in rows), D(0))
            solved = sum(bool(r["solved"]) for r in rows)
        if (published["solved"], D(published["usd"])) != (solved, total):
            problems.append(f"{label}: report says {published['solved']} solved / {published['usd']}, "
                            f"receipts give {solved} / {total}")
        if published.get("unmetered_review_calls", 0) != unmetered.get(arm, 0):
            problems.append(f"{label}: report says {published.get('unmetered_review_calls')} unmetered review calls, "
                            f"ledger has {unmetered.get(arm, 0)}")
        per_solved = f"{total / solved:.4f}" if solved else "n/a"
        note = "  + review on a subscription" if unmetered.get(arm) else ""
        print(f"{label[:76]:78s}{solved:>5d}/{len(rows):<3d}{total:>10.4f}{total / len(rows):>10.4f}{per_solved:>12s}{note}")
    if report["tasks_compared"] != len(common):
        problems.append(f"report compares {report['tasks_compared']} tasks, receipts pair {len(common)}")

    print()
    for problem in problems:
        print("MISMATCH:", problem)
    print("All figures recompute from the receipts." if not problems else f"{len(problems)} mismatch(es).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
