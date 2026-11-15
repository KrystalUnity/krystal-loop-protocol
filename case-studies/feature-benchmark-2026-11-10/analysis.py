#!/usr/bin/env python3
"""A second look at the feature benchmark: chance, task size, tokens and what the critics' findings were worth.

    python3 case-studies/feature-benchmark-2026-11-10/analysis.py           # recompute and compare
    python3 case-studies/feature-benchmark-2026-11-10/analysis.py --write   # rewrite analysis.json and ANALYSIS.md tables

Offline, standard library only. Reads results.json, ledger.jsonl, report.json, task-sizes.json and probes.json
from this folder. verify.py runs the comparison as its last check.

- Intervals are Wilson score intervals at 95%. Paired comparisons use the exact McNemar test: only the tasks
  where two arms disagree carry information, and the p-value is the two-sided binomial probability of a
  split at least that uneven if both arms were equally good.
- Task size is the dataset's reference solution: lines added plus lines removed. Tasks are ranked by it
  (ties by task id) and split into three groups of equal size.
- Tokens are the provider-reported usage in ledger.jsonl. A review arm carries the tokens of the worker
  run whose candidate it reviewed, the same way its cost does. Output includes reasoning tokens.
- Findings come from results.json; their probes' reruns on the reference solution from probes.json.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from decimal import ROUND_HALF_UP, Decimal as D
from pathlib import Path

HERE = Path(__file__).resolve().parent
Z95 = 1.959963984540054
LOW_COST = {"deepseek-flash"}

SOLO = ("astra-solo", "frontier-solo")
RUNS = (("Run 1", "klp:first", "klp"), ("Run 2", "worker", "klp-sol"), ("Run 3", "worker-3", "klp-3"))
LABELS = {
    "astra-solo": "Heavy model alone (`gpt-6-astra`)",
    "frontier-solo": "Frontier model alone (`gpt-6.1-sol`)",
    "klp:first": "Low-cost worker alone, run 1",
    "worker": "Low-cost worker alone, run 2",
    "worker-3": "Low-cost worker alone, run 3",
    "klp": "KLP Standard, run 1",
    "klp-sol": "KLP Standard, run 2",
    "klp-3": "KLP Standard, run 3",
}
SHORT = {"astra-solo": "heavy model alone", "frontier-solo": "frontier model alone", "klp:first": "its worker alone",
         "worker": "its worker alone", "worker-3": "its worker alone"}
CRITICS = {
    "klp-3": "`gpt-6.1-sol`, run 3",
    "klp-sol": "`gpt-6.1-sol`, run 2",
    "klp": "`gpt-6.1-sol`, run 1",
    "v2-sol": "`gpt-6.1-sol`, runner 0.5, run 2 candidates",
    "klp-astra": "`gpt-6-astra`, earlier runner, run 2 candidates",
    "klp-terra": "`gpt-6.1-terra`, earlier runner, run 2 candidates",
    "v2-grok": "`grok-4.7`, run 2 candidates",
    "v2-kimi": "Kimi K3.1 Pro (CLI), run 2 candidates",
    "v2-argon": "Gemini 4 Argon (CLI), run 2 candidates",
    "v2-qwen": "Qwen 3.8 Max (CLI), run 2 candidates",
    "v2a-sol": "`gpt-6.1-sol` + acceptance file, run 2 candidates",
    "klp-3a": "`gpt-6.1-sol` + acceptance file, run 3 candidates",
}
REPOSITORIES = (("pallets_click", "Click"), ("pallets_jinja", "Jinja"), ("samuelcolvin_dirty_equals", "dirty-equals"))
OUTCOMES = ("agrees", "asks_more", "inconclusive")


# ---------------------------------------------------------------- statistics

def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 0.0
    p, z2 = k / n, Z95 * Z95
    centre = (p + z2 / (2 * n)) / (1 + z2 / n)
    half = Z95 * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value for b and c discordant pairs."""
    n = b + c
    if n == 0:
        return 1.0
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n)


def lopsided_enough(n: int) -> int | None:
    """With n disagreements, the most the losing side may have for p < 0.05; None if no split would do."""
    best = None
    for j in range(n // 2 + 1):
        if mcnemar(n - j, j) < 0.05:
            best = j
    return best


# ---------------------------------------------------------------- data

def load() -> dict:
    results = json.loads((HERE / "results.json").read_text())
    by: dict = {}
    for row in results:
        by.setdefault(row["arm"], {})[row["task"]] = row
    report = json.loads((HERE / "report.json").read_text())
    return dict(by=by, report=report, tasks=sorted(by["klp-3"]),
                source={v["arm"]: v.get("candidates_from") for v in report["arms"].values()},
                sizes=json.loads((HERE / "task-sizes.json").read_text())["tasks"],
                probes=json.loads((HERE / "probes.json").read_text())["findings"],
                calls=[json.loads(line) for line in (HERE / "ledger.jsonl").read_text().splitlines()])


def solved(by: dict, arm: str, task: str) -> bool:
    if arm == "klp:first":  # run 1's worker, graded before review
        return bool(by["klp"][task]["first_candidate_solved"])
    return bool(by[arm][task]["solved"])


# ---------------------------------------------------------------- sections

def chance(d: dict) -> dict:
    by, tasks = d["by"], d["tasks"]
    intervals = {}
    for arm in LABELS:
        k = sum(solved(by, arm, t) for t in tasks)
        low, high = wilson(k, len(tasks))
        intervals[arm] = dict(solved=k, tasks=len(tasks), low=round(low, 4), high=round(high, 4))
    comparisons = []
    for run, worker, loop in RUNS:
        for other in (*SOLO, worker):
            loop_only = sum(solved(by, loop, t) and not solved(by, other, t) for t in tasks)
            other_only = sum(solved(by, other, t) and not solved(by, loop, t) for t in tasks)
            comparisons.append(dict(run=run, loop=loop, other=other, loop_only=loop_only, other_only=other_only,
                                    p=round(mcnemar(loop_only, other_only), 4),
                                    significant_if_other_at_most=lopsided_enough(loop_only + other_only)))
    return dict(intervals=intervals, comparisons=comparisons)


def size(d: dict) -> dict:
    by, tasks, sizes = d["by"], d["tasks"], d["sizes"]
    lines = {t: sizes[t]["reference"]["added"] + sizes[t]["reference"]["removed"] for t in tasks}
    ranked = sorted(tasks, key=lambda t: (lines[t], t))
    third = len(ranked) // 3
    members = {"small": ranked[:third], "medium": ranked[third:2 * third], "large": ranked[2 * third:],
               "one file": [t for t in tasks if sizes[t]["reference"]["files"] == 1],
               "two or more files": [t for t in tasks if sizes[t]["reference"]["files"] >= 2]}
    for prefix, name in REPOSITORIES:
        members[name] = [t for t in tasks if t.startswith(prefix + "-")]
    groups = {name: dict(tasks=len(ids), lines=[min(lines[t] for t in ids), max(lines[t] for t in ids)] if ids else None)
              for name, ids in members.items()}
    table = {arm: {name: sum(solved(by, arm, t) for t in ids) for name, ids in members.items()} for arm in LABELS}
    every_arm_missed = sorted(t for t in tasks if not any(solved(by, a, t) for a in by if a in LABELS or a in CRITICS)
                              and not solved(by, "klp:first", t))
    return dict(rule="reference solution lines added plus removed; ranked, ties by task id, three equal groups",
                groups=groups, solved=table,
                missed_by_every_arm=[dict(task=t, lines=lines[t], files=sizes[t]["reference"]["files"])
                                     for t in every_arm_missed])


def tokens(d: dict) -> dict:
    by, tasks, source = d["by"], set(d["tasks"]), d["source"]
    usage: dict = {}  # (arm, task, role) -> kind -> totals
    for call in d["calls"]:
        if call["status"] != "completed":
            continue
        arm, task = call["scope"].split("/", 1)
        if task not in tasks:
            continue
        kind = "unmetered" if call.get("metered") is False else "low_cost" if call["model"] in LOW_COST else "frontier"
        slot = usage.setdefault((arm, task, call["role"]), {}).setdefault(
            kind, dict(calls=0, input=0, cached=0, output=0, usd=D(0)))
        slot["calls"] += 1
        for key in ("input", "cached", "output"):
            slot[key] += (call.get("usage") or {}).get(key, 0)
        slot["usd"] += D(call["usd"]) if call.get("usd") is not None else D(0)
    out = {}
    for arm in LABELS:
        own, roles = ("klp", ("worker",)) if arm == "klp:first" else (arm, None)
        arms = {own} | ({source[own]} if source.get(own) and arm != "klp:first" else set())
        total = {k: dict(calls=0, input=0, cached=0, output=0, usd=D(0)) for k in ("low_cost", "frontier", "unmetered")}
        for (a, task, role), kinds in usage.items():
            if a in arms and (roles is None or role in roles):
                for kind, slot in kinds.items():
                    for key in slot:
                        total[kind][key] += slot[key]
        k = sum(solved(by, arm, t) for t in tasks)
        every = sum(total[x]["input"] + total[x]["output"] for x in ("low_cost", "frontier"))
        inputs = sum(total[x]["input"] for x in ("low_cost", "frontier"))
        usd = sum((total[x]["usd"] for x in total), D(0))
        out[arm] = dict(
            solved=k, calls=sum(total[x]["calls"] for x in total), unmetered_calls=total["unmetered"]["calls"],
            low_cost={key: total["low_cost"][key] for key in ("calls", "input", "cached", "output")},
            frontier={key: total["frontier"][key] for key in ("calls", "input", "cached", "output")},
            usd=str(usd),
            per_solved=dict(tokens=round(every / k), frontier=round((total["frontier"]["input"] + total["frontier"]["output"]) / k),
                            low_cost=round((total["low_cost"]["input"] + total["low_cost"]["output"]) / k),
                            fresh_input=round(sum(total[x]["input"] - total[x]["cached"] for x in ("low_cost", "frontier")) / k),
                            usd=str(usd / k)),
            cached_share_of_input=round(sum(total[x]["cached"] for x in ("low_cost", "frontier")) / inputs, 4) if inputs else None)
    return out


def findings(d: dict) -> dict:
    by, tasks, probes = d["by"], d["tasks"], d["probes"]
    out = {}
    for arm in CRITICS:
        rows = [by[arm][t] for t in tasks]
        dispositions = {k: sum(v["dispositions"].count(k) for r in rows for v in r["reviews"])
                        for k in ("confirmed", "refuted", "unverified", "advisory")}
        probed = dispositions["confirmed"] + dispositions["refuted"]
        first = dict(failing=0, failing_flagged=0, rescued=0, passing=0, passing_flagged=0, broken=0, not_reviewed=0)
        for r in rows:
            if not r["reviews"]:
                first["not_reviewed"] += 1
                continue
            flagged = "confirmed" in r["reviews"][0]["dispositions"]
            side = "passing" if r["first_candidate_solved"] else "failing"
            first[side] += 1
            first[side + "_flagged"] += flagged
            first["rescued"] += bool(r["solved"] and not r["first_candidate_solved"])
            first["broken"] += bool(r["first_candidate_solved"] and not r["solved"])
        mine = [p for p in probes if p["arm"] == arm]
        kept = [p for p in mine if p["retained"]]
        same = [p for p in kept if p.get("reproduced")]
        confirmed = [p for p in same if p["disposition"] == "confirmed"]
        reference = {k: sum(p["reference"]["outcome"] == k for p in confirmed) for k in OUTCOMES}
        on_passing = {k: sum(p["reference"]["outcome"] == k for p in confirmed if p["candidate_passed_hidden_tests"])
                      for k in OUTCOMES}
        on_failing = {k: sum(p["reference"]["outcome"] == k for p in confirmed if not p["candidate_passed_hidden_tests"])
                      for k in OUTCOMES}
        out[arm] = dict(
            dispositions=dispositions, withdrawn=sum(v.get("withdrawn", 0) for r in rows for v in r["reviews"]),
            confirmation_rate=round(dispositions["confirmed"] / probed, 4) if probed else None,
            first_review=first,
            probes=dict(recorded=len(mine), retained=len(kept), reproduced=len(same),
                        confirmed_checked=len(confirmed),
                        confirmed_recorded=sum(p["disposition"] == "confirmed" for p in mine)),
            reference=reference, reference_on_passing_candidates=on_passing, reference_on_failing_candidates=on_failing)
    return out


def consistency(d: dict) -> list[str]:
    """probes.json must describe the same findings and grades as results.json."""
    problems = []
    by = d["by"]
    for arm in CRITICS:
        rows = [by[arm][t] for t in d["tasks"]]
        mine = [p for p in d["probes"] if p["arm"] == arm]
        for kind in ("confirmed", "refuted"):
            recorded = sum(v["dispositions"].count(kind) for r in rows for v in r["reviews"])
            listed = sum(p["disposition"] == kind for p in mine)
            if recorded != listed:
                problems.append(f"{arm}: results.json has {recorded} {kind} findings, probes.json {listed}")
    for p in d["probes"]:
        grade = by[p["arm"]][p["task"]]["grades"].get(p["reviewed_revision"])
        if grade is None or bool(grade["passed"]) != p["candidate_passed_hidden_tests"]:
            problems.append(f"{p['arm']}/{p['task']} {p['id']}: hidden-test grade of the reviewed candidate differs")
    return problems


def analyse() -> tuple[dict, list[str]]:
    d = load()
    return dict(tasks=len(d["tasks"]), chance=chance(d), size=size(d), tokens=tokens(d), findings=findings(d)), consistency(d)


# ---------------------------------------------------------------- tables

def pct(x: float) -> str:
    return f"{round(100 * x)}%"


def count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1e6:.1f}M"
    if n >= 10_000:
        return f"{n / 1000:.0f}k"
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


def dollars(text: str) -> str:
    return "$" + str(D(text).quantize(D("0.001"), rounding=ROUND_HALF_UP))


def table(header: list[str], rows: list[list], align: str) -> str:
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join("---" if a == "l" else "---:" for a in align) + " |"]
    lines += ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def render(a: dict) -> dict[str, str]:
    c, s, t, f = a["chance"], a["size"], a["tokens"], a["findings"]
    blocks = {}
    blocks["intervals"] = table(
        ["66 tasks", "Tasks solved", "95% interval"],
        [[LABELS[arm], f"{v['solved']} ({pct(v['solved'] / v['tasks'])})", f"{pct(v['low'])} to {pct(v['high'])}"]
         for arm, v in c["intervals"].items()], "lrr")
    blocks["comparisons"] = table(
        ["KLP Standard", "Against", "Only the loop solved", "Only the other solved", "p", "Needed for p < 0.05"],
        [[f"{x['run']} ({c['intervals'][x['loop']]['solved']})",
          f"{SHORT[x['other']]} ({c['intervals'][x['other']]['solved']})", x["loop_only"], x["other_only"],
          f"{x['p']:.2f}",
          "no split" if x["significant_if_other_at_most"] is None else
          f"{x['loop_only'] + x['other_only'] - x['significant_if_other_at_most']} to {x['significant_if_other_at_most']}"]
         for x in c["comparisons"]], "llrrrr")
    g = s["groups"]
    names = ["small", "medium", "large", "one file", "two or more files"]
    head = [f"Small, {g['small']['lines'][0]}–{g['small']['lines'][1]} lines",
            f"Medium, {g['medium']['lines'][0]}–{g['medium']['lines'][1]}",
            f"Large, {g['large']['lines'][0]}–{g['large']['lines'][1]}", "One file", "Two files"]
    blocks["size"] = table(["Tasks solved"] + head,
                           [[LABELS[arm]] + [s["solved"][arm][n] for n in names] for arm in LABELS]
                           + [["Tasks in the group"] + [g[n]["tasks"] for n in names]], "lrrrrr")
    repos = [name for _, name in REPOSITORIES]
    blocks["repositories"] = table(["Tasks solved"] + [f"{r} ({g[r]['tasks']})" for r in repos],
                                   [[LABELS[arm]] + [s["solved"][arm][r] for r in repos] for arm in LABELS], "lrrr")
    blocks["tokens"] = table(
        ["66 tasks", "Solved", "Tokens per solved task", "Frontier-model tokens", "Low-cost-model tokens",
         "Fresh input", "Input read from cache", "Cost per solved task"],
        [[LABELS[arm], v["solved"], count(v["per_solved"]["tokens"]), count(v["per_solved"]["frontier"]),
          count(v["per_solved"]["low_cost"]), count(v["per_solved"]["fresh_input"]),
          pct(v["cached_share_of_input"]), dollars(v["per_solved"]["usd"])] for arm, v in t.items()],
        "lrrrrrrr")
    blocks["dispositions"] = table(
        ["Critic", "Settled by a probe", "Confirmed: probe failed", "Discarded: probe passed", "Confirmed share",
         "Advisory or unproven", "Withdrawn"],
        [[CRITICS[arm], v["dispositions"]["confirmed"] + v["dispositions"]["refuted"], v["dispositions"]["confirmed"],
          v["dispositions"]["refuted"], pct(v["confirmation_rate"]) if v["confirmation_rate"] is not None else "n/a",
          v["dispositions"]["advisory"] + v["dispositions"]["unverified"], v["withdrawn"]] for arm, v in f.items()],
        "lrrrrrr")
    blocks["first_review"] = table(
        ["Critic", "Candidates failing the hidden tests", "Flagged", "Rescued", "Candidates passing them", "Flagged",
         "Broken"],
        [[CRITICS[arm], v["first_review"]["failing"], v["first_review"]["failing_flagged"], v["first_review"]["rescued"],
          v["first_review"]["passing"], v["first_review"]["passing_flagged"], v["first_review"]["broken"]]
         for arm, v in f.items()], "lrrrrrr")
    blocks["reference"] = table(
        ["Critic", "Confirmed findings rerun", "Reference agrees", "Asks for more", "Cannot run on it",
         "On candidates passing the hidden tests: agrees / asks for more / cannot run"],
        [[CRITICS[arm], f"{v['probes']['confirmed_checked']} of {v['probes']['confirmed_recorded']}",
          v["reference"]["agrees"], v["reference"]["asks_more"], v["reference"]["inconclusive"],
          " / ".join(str(v["reference_on_passing_candidates"][k]) for k in OUTCOMES)]
         for arm, v in f.items() if v["probes"]["confirmed_recorded"]], "lrrrrr")
    return blocks


def replace_blocks(text: str, blocks: dict[str, str]) -> str:
    for name, body in blocks.items():
        pattern = re.compile(rf"(<!-- table:{name} -->\n)(?:.*?\n)?(<!-- /table:{name} -->)", re.S)
        if not pattern.search(text):
            raise SystemExit(f"ANALYSIS.md has no table:{name} block")
        text = pattern.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)
    return text


def check(write: bool = False) -> list[str]:
    analysis, problems = analyse()
    doc = HERE / "ANALYSIS.md"
    fresh = json.dumps(analysis, indent=1) + "\n"
    rendered = replace_blocks(doc.read_text(), render(analysis))
    if write:
        (HERE / "analysis.json").write_text(fresh)
        doc.write_text(rendered)
        return problems
    if (HERE / "analysis.json").read_text() != fresh:
        problems.append("analysis.json differs from what the receipts give; rerun analysis.py --write")
    if doc.read_text() != rendered:
        problems.append("a table in ANALYSIS.md differs from what the receipts give; rerun analysis.py --write")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="rewrite analysis.json and the tables in ANALYSIS.md")
    args = parser.parse_args()
    problems = check(write=args.write)
    for problem in problems:
        print("MISMATCH:", problem)
    if not problems:
        print("analysis.json and the ANALYSIS.md tables recompute from the receipts." if not args.write else
              "wrote analysis.json and the ANALYSIS.md tables.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
