#!/usr/bin/env python3
"""Recompute every published figure of the feature benchmark from its receipts. Offline, standard library only.

    python3 case-studies/feature-benchmark-2026-11-10/verify.py

Checks, in order:
1. each model call's cost equals its reported token usage times the recorded price;
2. each run's cost equals the sum of its calls;
3. the report's solve counts and totals equal what the per-run results add up to.

A KLP arm reviews the candidates built by the `worker` arm, so its cost is its own critic and
repair calls plus the worker calls for the same task.
"""
from __future__ import annotations

import json
import sys
from decimal import Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent


def price(usage: dict, rates: dict) -> D:
    r = {k: D(str(v)) for k, v in rates.items()}
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
    for call in calls:
        if call["status"] != "completed":
            continue
        expected = price(call["usage"], prices[call["model"]])
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
    print(f"{'':50s}{'solved':>8s}{'total USD':>12s}{'per task':>11s}{'per solved':>12s}")
    for label, published in report["arms"].items():
        arm = published["arm"]
        if arm == "klp:first-candidate":  # the single-pass KLP arm's worker, graded before review
            rows = [arms["klp"][task] for task in common]
            total = sum((D(r["effort"].get("worker", {}).get("usd", "0")) for r in rows), D(0))
            solved = sum(bool(r["first_candidate_solved"]) for r in rows)
        else:
            rows = [arms[arm][task] for task in common]
            built = arms.get("worker", {}) if arm.startswith("klp-") else {}
            total = sum((D(r["usd"]) + (D(built[r["task"]]["usd"]) if r["task"] in built else D(0)) for r in rows), D(0))
            solved = sum(bool(r["solved"]) for r in rows)
        if (published["solved"], D(published["usd"])) != (solved, total):
            problems.append(f"{label}: report says {published['solved']} solved / {published['usd']}, "
                            f"receipts give {solved} / {total}")
        per_solved = f"{total / solved:.4f}" if solved else "n/a"
        print(f"{label:50s}{solved:>5d}/{len(rows):<3d}{total:>11.4f}{total / len(rows):>11.4f}{per_solved:>12s}")
    if report["tasks_compared"] != len(common):
        problems.append(f"report compares {report['tasks_compared']} tasks, receipts pair {len(common)}")

    print()
    for problem in problems:
        print("MISMATCH:", problem)
    print("All figures recompute from the receipts." if not problems else f"{len(problems)} mismatch(es).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
