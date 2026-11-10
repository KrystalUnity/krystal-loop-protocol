"""KLP Standard as one function: bounded work, executed checks, independent review, one receipt.

    worker builds  ->  runner executes the declared checks  ->  an independent critic reviews
    the exact candidate  ->  findings are settled by running their probes  ->  confirmed
    blockers get a bounded repair  ->  the repair is re-checked and re-reviewed  ->  receipt.

The worker never accepts its own work, review is bound to an exact commit, required checks
actually run, and time, cost and repair attempts are finite. A confirmed finding stays open
until its probe passes or the critic withdraws it. Merging, pushing and deploying stay with you.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from decimal import Decimal as D
from pathlib import Path

from .llm import BudgetExceeded, Ledger, Model, ProviderError
from .review import adjudicate, build_packet, candidate_diff, project_test_rules, review, run_acceptance
from .sandbox import Sandbox, clip
from .snapshot import Snapshots
from .worker import run_worker

PROTOCOL = "klp-standard/v0.2"


@dataclass
class Limits:
    max_steps: int = 100         # worker turns for the first build
    repair_steps: int = 40       # worker turns for each repair
    repair_rounds: int = 2
    command_timeout: float = 300
    check_timeout: float = 900
    cost_usd: float = 2.0        # per task, all roles
    time_seconds: float = 3600


def _run_checks(sandbox: Sandbox, checks: list[str], timeout: float) -> list:
    results = []
    for command in checks:
        result = sandbox.run(command, timeout=timeout, limit=6000)
        results.append(dict(command=command, passed=result["returncode"] == 0, **result))
    return results


def _repair_prompt(failed_checks: list, confirmed: list) -> str:
    parts = ["An independent review of your change found problems that are confirmed by executed evidence. "
             "Fix them inside the original task. If a probe expects something the task statement does not "
             "require, leave that behaviour alone and say so in your handover."]
    for check in failed_checks:
        parts.append(f"## Declared check failed\n$ {check['command']}\nexit code: {check['returncode']}\n{clip(check['output'], 3000)}")
    for finding in confirmed:
        probe = finding["probe"]
        parts.append(f"## Finding {finding['id']} (confirmed: its probe fails)\n{finding['claim']}\n"
                     f"Probe file: {probe['file']}\n$ {probe['command']}\nexit code: {probe['returncode']}\n{clip(probe['output'], 2500)}")
    parts.append("When fixed, re-run the failing commands above, then give your handover.")
    return "\n\n".join(parts)


def run_standard(*, ledger: Ledger, worker: Model, critic: Model | None, sandbox: Sandbox, task: str,
                 checks: list[str], scope: str, limits: Limits, out_dir: Path, task_id: str = "",
                 critical_triggers: list[str] | None = None, project_revision: str = "",
                 resume: dict | None = None, acceptance: bool = False) -> dict:
    """Run one task. `critic=None` runs the worker alone (no review, no repair) for comparison arms.

    `acceptance` asks the critic, on its first review, for a test file covering each behaviour the task
    statement spells out. The runner executes it and every failing test is a confirmed finding.

    `resume` continues from a recorded unreviewed run: {"receipt": that run's receipt, "messages": its
    worker transcript}. The workspace and snapshot store must be copies of that run's. The build is
    not repeated; review and repair start from the recorded candidate.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()
    ledger.scope_caps[scope] = D(str(limits.cost_usd))
    if critic is not None and critic.family == worker.family:
        raise ValueError("worker and critic must be different model families for an independent review")
    snapshots = Snapshots(sandbox, out_dir / "snapshots")
    base = resume["receipt"]["base_revision"] if resume else snapshots.take("base")
    receipt: dict = dict(
        protocol=PROTOCOL, task_id=task_id or scope, base_revision=base, project_revision=project_revision,
        before_work=dict(task=task, checks=checks, limits=asdict(limits), critical_triggers=list(critical_triggers or []),
                         worker=dict(model=worker.name, family=worker.family),
                         critic=None if critic is None else dict(model=critic.name, family=critic.family),
                         acceptance_file=bool(acceptance and critic is not None),
                         forbidden_actions="network access, merge, push, deploy"),
        candidates=[], reviews=[], repairs=[], errors=[])
    state, session, final, rules = "completed", None, base, None

    def record_candidate(label: str, handover: str | None) -> dict:
        revision = snapshots.take(label)
        entry = dict(label=label, revision=revision, checks=_run_checks(sandbox, checks, limits.check_timeout),
                     handover=handover)
        entry["checks_passed"] = all(c["passed"] for c in entry["checks"])
        receipt["candidates"].append(entry)
        return entry

    def review_candidate(entry: dict, since: str, prior: list | None, still_open: list) -> list:
        number = len(receipt["reviews"]) + 1
        diff = candidate_diff(snapshots, since, entry["revision"])
        packet = build_packet(task, diff, entry["checks"], entry["handover"], prior=prior, triggers=critical_triggers,
                              rules=rules)
        (out_dir / f"review-packet-{number}.md").write_text(packet)
        verdict = review(ledger, critic, packet, scope=scope, acceptance=acceptance and number == 1, rereview=number > 1)
        settled = adjudicate(sandbox, snapshots, verdict, entry["revision"], rules=rules)
        ran = None
        if verdict["acceptance"]:
            ran, found = run_acceptance(sandbox, snapshots, verdict["acceptance"], entry["revision"], rules=rules)
            settled += found
        if number > 1:
            for finding in settled:  # ids restart in every reply; keep them unique across the run
                finding["id"] = f"R{number}-{finding['id']}"
        withdrawn = [f["id"] for f in still_open if f["id"] in verdict["withdrawn"]]
        settled += [f for f in still_open if f["id"] not in withdrawn]
        receipt["reviews"].append(dict(reviewed_revision=entry["revision"], model=verdict["model"], family=verdict["family"],
                                       verdict=verdict["verdict"], profile_assessment=verdict["profile_assessment"],
                                       attempts=verdict["attempts"], packet_bytes=verdict["packet_bytes"],
                                       diff_bytes=diff["bytes"], diff_truncated=diff["truncated"], findings=settled,
                                       acceptance=ran, withdrawn=withdrawn))
        return settled

    try:
        if resume:
            candidate = dict(resume["receipt"]["candidates"][0])
            snapshots.restore(candidate["revision"])
            receipt["candidates"].append(candidate)
            receipt["errors"] += resume["receipt"]["errors"]
            receipt["resumed_from"] = resume["receipt"]["task_id"]
            session = dict(messages=resume["messages"], handover=candidate["handover"], finished=True, steps=0)
        else:
            session = run_worker(ledger, worker, sandbox, task, scope=scope, max_steps=limits.max_steps,
                                 command_timeout=limits.command_timeout)
            candidate = record_candidate("candidate", session["handover"])
            if not session["finished"]:
                receipt["errors"].append("worker used all its steps without handing over")
        final = candidate["revision"]
        if critic is None:
            state = "unreviewed"
        else:
            rules = project_test_rules(sandbox)
            receipt["probe_rules"] = rules and rules["file"]
            settled = review_candidate(candidate, base, None, [])
            if receipt["reviews"][-1]["profile_assessment"] == "critical_trigger":
                state = "critical_trigger"
            confirmed = [f for f in settled if f["disposition"] == "confirmed"]
            failed = [c for c in candidate["checks"] if not c["passed"]]
            rounds = 0
            while state == "completed" and (confirmed or failed) and rounds < limits.repair_rounds:
                if time.time() - started > limits.time_seconds:
                    state = "budget_exhausted"
                    break
                rounds += 1
                session = run_worker(ledger, worker, sandbox, _repair_prompt(failed, confirmed), scope=scope,
                                     max_steps=limits.repair_steps, command_timeout=limits.command_timeout,
                                     messages=session["messages"], role="repair")
                repaired = record_candidate(f"repair-{rounds}", session["handover"])
                probes, still_open = [], []
                for finding in confirmed:
                    again = sandbox.run(finding["probe"]["command"], timeout=180, limit=2000)
                    snapshots.restore(repaired["revision"])
                    probes.append(dict(id=finding["id"], command=finding["probe"]["command"],
                                       returncode=again["returncode"], closed=again["returncode"] == 0))
                    if again["returncode"] != 0:  # stays open on the repaired candidate, with its latest output
                        still_open.append({**finding, "carried": True, "probe": {
                            **finding["probe"], "returncode": again["returncode"], "timed_out": again["timed_out"],
                            "output": again["output"]}})
                receipt["repairs"].append(dict(round=rounds, from_revision=candidate["revision"],
                                               to_revision=repaired["revision"], steps=session["steps"], probes=probes,
                                               checks_passed=repaired["checks_passed"]))
                if candidate["checks_passed"] and not repaired["checks_passed"]:
                    # Never trade a candidate that passes its checks for one that does not.
                    snapshots.restore(candidate["revision"])
                    receipt["repairs"][-1]["kept"] = False
                    state = "budget_exhausted"
                    break
                receipt["repairs"][-1]["kept"] = True
                prior = [dict(id=f["id"], claim=f["claim"], disposition=f["disposition"],
                              closed_after_repair=next((p["closed"] for p in probes if p["id"] == f["id"]), None))
                         for f in settled]
                settled = review_candidate(repaired, candidate["revision"], prior, still_open)
                candidate, final = repaired, repaired["revision"]
                confirmed = [f for f in settled if f["disposition"] == "confirmed"]
                failed = [c for c in candidate["checks"] if not c["passed"]]
            if state == "completed" and (confirmed or failed):
                state = "budget_exhausted"
    except BudgetExceeded as error:
        state = "budget_exhausted"
        receipt["errors"].append(str(error))
    except ProviderError as error:
        state = "blocked"
        receipt["errors"].append(str(error))
    if receipt["candidates"] and final == base:
        final = receipt["candidates"][-1]["revision"]
    elif not receipt["candidates"]:
        final = snapshots.take("partial")  # whatever the worker left behind, for inspection
    if session:
        (out_dir / "worker-transcript.json").write_text(json.dumps(session["messages"], indent=1))
    last_review = receipt["reviews"][-1] if receipt["reviews"] else None
    receipt["completion"] = dict(
        state=state, final_revision=final,
        checks_passed=next((c["checks_passed"] for c in receipt["candidates"] if c["revision"] == final), None),
        unresolved_findings=[] if not last_review else
        [f for f in last_review["findings"] if f["disposition"] in ("confirmed", "unverified")],
        measured_effort=dict(seconds=round(time.time() - started, 1), by_role=ledger.summary(scope=scope),
                             usd=str(ledger.spent(scope=scope))),
        human_decisions_required="merge, push and deploy")
    (out_dir / "receipt.json").write_text(json.dumps(receipt, indent=1))
    (out_dir / "receipt.md").write_text(render_receipt(receipt))
    return receipt


def render_receipt(receipt: dict) -> str:
    done, effort = receipt["completion"], receipt["completion"]["measured_effort"]
    lines = [f"# KLP Standard receipt: {receipt['task_id']}", "",
             f"- protocol: {receipt['protocol']}", f"- state: **{done['state']}**",
             f"- project revision: `{receipt.get('project_revision') or 'not recorded'}`",
             f"- base snapshot: `{receipt['base_revision']}`", f"- final snapshot: `{done['final_revision']}`",
             f"- declared checks on final revision: {'passed' if done['checks_passed'] else 'NOT passed'}",
             f"- worker: {receipt['before_work']['worker']['model']}",
             f"- critic: {(receipt['before_work']['critic'] or {}).get('model', 'none (unreviewed run)')}",
             f"- elapsed: {effort['seconds']}s, cost: ${float(effort['usd']):.4f}", ""]
    for role, s in effort["by_role"].items():
        if s.get("unmetered_calls"):
            lines.append(f"  - {role}: {s['calls']} calls on a subscription route, not metered")
            continue
        lines.append(f"  - {role}: {s['calls']} calls, {s['input']:,} input tokens ({s['cached']:,} cached), "
                     f"{s['output']:,} output, ${float(s['usd']):.4f}")
    for number, item in enumerate(receipt["reviews"], 1):
        lines += ["", f"## Review {number}: {item['verdict']} on `{item['reviewed_revision'][:12]}` "
                      f"({item['model']}, profile {item['profile_assessment']})"]
        ran = item.get("acceptance")
        if ran:
            lines.append(f"- acceptance file: {ran['result']}"
                         + (f" ({len(ran['failed_tests'])} failing: {', '.join(ran['failed_tests'][:8])})" if ran["failed_tests"] else ""))
        for f in item["findings"]:
            lines.append(f"- [{f['disposition']}{', still open from an earlier review' if f.get('carried') else ''}] "
                         f"{f['id']}: {f['claim']}")
        if item.get("withdrawn"):
            lines.append(f"- withdrawn by the critic: {', '.join(item['withdrawn'])}")
    for repair in receipt["repairs"]:
        closed = sum(p["closed"] for p in repair["probes"])
        lines += ["", f"## Repair {repair['round']}: {closed}/{len(repair['probes'])} confirmed findings closed, "
                      f"checks {'passed' if repair['checks_passed'] else 'failed'}, "
                      f"{'kept' if repair.get('kept') else 'discarded'}"]
    if receipt["errors"]:
        lines += ["", "## Stops and errors"] + [f"- {e}" for e in receipt["errors"]]
    lines += ["", f"Still yours to decide: {done['human_decisions_required']}.", ""]
    return "\n".join(lines)
