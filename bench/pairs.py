#!/usr/bin/env python3
"""Paired-feature benchmark: two workers, two features, one tree.

Each pair is two features of the same library whose reference patches conflict when merged. Both features
are already built and individually pass their hidden tests (they come from a finished `features.py` arm).
What is measured is the integration: getting both into one tree that passes both features' hidden tests.

    python3 -m bench.pairs select --work ~/klp-bench --pairs 30
    python3 -m bench.pairs run    --work ~/klp-bench --arms merge,chat,semio,solo --cap 20
    python3 -m bench.pairs report --work ~/klp-bench

Arms, all starting from the same two candidates:
  merge   git merges the two patches. No model.
  chat    agent-managed: both workers are woken, each can read the other's patch, and they agree in
          free-text messages who integrates.
  semio   each worker's finished work is a typed handover through the Semio adapter. Software merges; when
          the merge needs a person-like decision, exactly one worker is woken with the exact artifact.
  solo    one frontier model implements both features alone, from scratch.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import copy
import hashlib
import json
import random
import shutil
import statistics
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "examples" / "semio-coordination"))

from bench.features import GIT, MODELS, PYTEST, box, fresh_workspace, hidden_grade, sh  # noqa: E402
from klp.llm import Ledger, Model, ProviderError, BudgetExceeded, clean_message  # noqa: E402
from klp.sandbox import clip  # noqa: E402
from klp.snapshot import Snapshots  # noqa: E402
from klp.standard import Limits, run_standard  # noqa: E402
from klp.worker import BASH_TOOL, run_worker  # noqa: E402
from semio_adapter import SemioAdapter  # noqa: E402

SOURCE_ARM = "klp-3"       # finished single-feature runs the pair candidates come from
BUILDER_ARMS = ("worker-3", "klp-3")
ARMS = {"merge": "Plain git merge, no coordination",
        "chat": "Agent-managed: both workers woken, free-text messages",
        "semio": "Semio: typed handovers, software merges, one worker woken when needed",
        "solo": "Frontier model alone builds both features (gpt-6.1-sol)"}
INTEGRATE_STEPS = 40

MESSAGE_TOOL = {"type": "function", "function": {
    "name": "send_message",
    "description": "Send a short message to your teammate. They read it before their next step.",
    "parameters": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}}}


# ---------------------------------------------------------------- pairs

def select(work: Path, count: int, seed: int) -> None:
    tasks = {t["id"]: t for t in json.loads((work / "tasks.json").read_text())["tasks"] if t["valid"]}
    dataset = Path(next(iter(tasks.values()))["statement"]).parents[3]
    gold = json.loads((dataset / "gold_conflict_report.json").read_text())["conflict_pairs"]
    solved = {p.parent.name for p in (work / "runs" / SOURCE_ARM).glob("*/result.json")
              if json.loads(p.read_text()).get("solved")}
    groups: dict[str, list] = {}
    for row in gold:
        prefix = f"{row['repo'].removesuffix('_task')}-task{row['task_id']}"
        a, b = f"{prefix}-feature{row['f1']}", f"{prefix}-feature{row['f2']}"
        if a in solved and b in solved:
            groups.setdefault(prefix, []).append((a, b))
    rng = random.Random(seed)
    for rows in groups.values():
        rows.sort()
        rng.shuffle(rows)
    chosen = []
    while len(chosen) < count and any(groups.values()):  # round-robin over the base commits
        for prefix in sorted(groups):
            if groups[prefix] and len(chosen) < count:
                a, b = groups[prefix].pop()
                chosen.append(dict(id=f"{prefix}-f{a.rsplit('feature', 1)[1]}+f{b.rsplit('feature', 1)[1]}", a=a, b=b))
    (work / "pairs.json").write_text(json.dumps(dict(
        source_arm=SOURCE_ARM, seed=seed, eligible=sum(len(v) for v in groups.values()) + len(chosen), pairs=chosen), indent=1))
    print(f"selected {len(chosen)} pairs from {sum(len(v) for v in groups.values()) + len(chosen)} eligible conflicting pairs")


def side(work: Path, out: Path, task: dict, name: str) -> dict:
    """A private copy of one finished feature: workspace, snapshot store, worker session and patch."""
    source = work / "runs" / SOURCE_ARM / task["id"]
    ws, store = out / f"ws-{name}", out / f"snapshots-{name}"
    sh("cp", "-a", str(source / "ws"), str(ws))
    sh("cp", "-a", str(source / "snapshots"), str(store))
    receipt = json.loads((source / "receipt.json").read_text())
    sandbox = box(ws, work / "envs" / task["env"])
    snapshots = Snapshots(sandbox, store)
    final = receipt["completion"]["final_revision"]
    snapshots.restore(final)
    patch = snapshots.patch(receipt["base_revision"], final)
    statement = Path(task["statement"]).read_text().strip()
    return dict(name=name, task=task, sandbox=sandbox, snapshots=snapshots, base=receipt["base_revision"], final=final,
                patch=patch, statement=statement, title=statement.splitlines()[0].replace("**Title**:", "").strip(),
                check=f"{PYTEST} -x {' '.join(task['test_files'])}",
                messages=json.loads((source / "worker-transcript.json").read_text()))


def try_merge(env_dir: Path, scratch: Path, first: bytes, second: bytes, commit: str) -> dict:
    """Apply both patches to a pristine checkout the way git would merge them. No model."""
    ws = fresh_workspace(env_dir, scratch)
    (ws / "first.patch").write_bytes(first)
    (ws / "second.patch").write_bytes(second)
    sandbox = box(ws, env_dir)
    identity = "-c user.name=klp -c user.email=klp@localhost"
    done = sandbox.run(f"{GIT} apply --binary --whitespace=nowarn /workspace/first.patch && {GIT} add -A "
                       f"&& {GIT} {identity} commit -qm first && {GIT} apply --3way --whitespace=nowarn /workspace/second.patch",
                       limit=3000)
    if done["returncode"] != 0:
        files = sandbox.run(f"{GIT} diff --name-only --diff-filter=U", limit=2000)["output"].split()
        return dict(clean=False, output=done["output"], conflict_files=files, patch=None, sandbox=sandbox)
    raw = sandbox.run(f"{GIT} add -A && {GIT} diff --binary --cached {commit}", limit=None)
    return dict(clean=True, output="", conflict_files=[], patch=raw["raw"], sandbox=sandbox)


def visible_checks(sandbox, sides: list) -> list:
    out = []
    for command in dict.fromkeys(s["check"] for s in sides):
        result = sandbox.run(command, timeout=900, limit=4000)
        out.append(dict(command=command, passed=result["returncode"] == 0, returncode=result["returncode"],
                        output=result["output"]))
    return out


def grade(work: Path, out: Path, pair_sides: list, patch: bytes | None) -> dict:
    grades = {}
    for s in pair_sides:
        task = s if "env" in s else s["task"]
        grades[task["id"]] = (hidden_grade(work / "envs" / task["env"], out / "grade", task, candidate=patch)
                              if patch else dict(passed=False, stage="no tree"))
    return grades


# ---------------------------------------------------------------- chat arm

CHAT_NOTE = """New assignment. Your teammate has finished another feature on the same base commit:

{peer_title}

Your change and theirs must end up in ONE tree that passes both features' tests. Their task statement is at
/workspace/handover/peer-task.md and their finished change is the patch /workspace/handover/peer.patch.
Their tests: $ {peer_check}
Your tests:  $ {own_check}

You and your teammate decide between you who integrates. Use send_message to talk to them.
- If you integrate: bring their change into your workspace, resolve any conflicts, run both test commands,
  then reply WITHOUT a tool call, starting with the word INTEGRATED, and say what you did.
- If your teammate integrates: reply WITHOUT a tool call, starting with the words STANDING BY."""


def run_chat(ledger: Ledger, model: Model, sides: list, scope: str) -> dict:
    """Both workers are live. Turns alternate; a message wakes its recipient."""
    state = {}
    for own, peer in ((sides[0], sides[1]), (sides[1], sides[0])):
        own["sandbox"].write_file("/workspace/handover/peer.patch", peer["patch"].decode("utf-8", "replace"))
        own["sandbox"].write_file("/workspace/handover/peer-task.md", peer["statement"])
        history = list(own["messages"])
        history.append({"role": "user", "content": CHAT_NOTE.format(peer_title=peer["title"], peer_check=peer["check"],
                                                                    own_check=own["check"])})
        state[own["name"]] = dict(side=own, history=history, inbox=[], status=None, steps=0, sent=0, declared_at=None)
    order, clock, nudged = [s["name"] for s in sides], 0, False
    while True:
        active = [n for n in order if (state[n]["status"] is None or state[n]["inbox"]) and state[n]["steps"] < INTEGRATE_STEPS]
        if not active:
            if not nudged and not any(state[n]["status"] == "INTEGRATED" for n in order) \
                    and all(state[n]["steps"] < INTEGRATE_STEPS for n in order):
                nudged = True  # both stood by: say so once, in plain words, as a human lead would
                for n in order:
                    state[n]["inbox"].append("Coordinator: nobody has integrated yet. One of you must.")
                continue
            break
        for name in active:
            me = state[name]
            other = state[[n for n in order if n != name][0]]
            if me["inbox"]:
                me["history"].append({"role": "user", "content": "\n\n".join(me["inbox"])})
                me["inbox"], me["status"] = [], None
            me["steps"] += 1
            clock += 1
            reply = ledger.chat(model, me["history"], role="chat", scope=scope, tools=BASH_TOOL + [MESSAGE_TOOL])
            me["history"].append(clean_message(reply))
            calls = reply.get("tool_calls") or []
            if not calls:
                text = (reply.get("content") or "").strip()
                if not text and reply.get("_finish_reason") == "length":
                    me["history"].append({"role": "user", "content": "Your reply was cut off. Continue."})
                    continue
                me["status"] = "INTEGRATED" if text.upper().startswith("INTEGRATED") else "STANDING BY"
                me["declared_at"], me["handover"] = clock, text
                continue
            for call in calls:
                try:
                    arguments = json.loads(call["function"]["arguments"])
                    if call["function"]["name"] == "send_message":
                        other["inbox"].append(f"Message from your teammate:\n{str(arguments['text'])[:4000]}")
                        me["sent"] += 1
                        content = "delivered"
                    else:
                        content = json.dumps(me["side"]["sandbox"].run(arguments["command"], timeout=300))
                except (KeyError, TypeError, ValueError) as error:
                    content = f"invalid tool call: {error}"
                me["history"].append({"role": "tool", "tool_call_id": call.get("id", ""), "content": content})
    declared = sorted((state[n] for n in order if state[n]["status"] == "INTEGRATED"), key=lambda s: s["declared_at"])
    return dict(integrator=declared[0] if declared else None, double_integration=len(declared) > 1,
                messages=sum(state[n]["sent"] for n in order), steps={n: state[n]["steps"] for n in order},
                sessions_woken=2, state=state)


# ---------------------------------------------------------------- semio arm

class MemoryTransport:
    """The stream interface the Semio adapter expects, held in memory for one pair."""

    def __init__(self):
        self.entries, self.reads = [], 0

    def publish(self, *, sender, to, kind, payload_dict, correlation_id=None, in_reply_to=None, nexus_ref=None):
        entry = dict(id=f"{len(self.entries) + 1}-0", v="1", kind=kind, payload=copy.deepcopy(payload_dict),
                     correlation_id=correlation_id, in_reply_to=in_reply_to or "", nexus_ref=nexus_ref or "")
        entry.update({"from": sender, "to": to})
        self.entries.append(entry)
        return entry["id"]

    def read_entry(self, entry_id):
        return next((copy.deepcopy(e) for e in self.entries if e["id"] == entry_id), None)

    def read_since(self, last_id="0-0", count=100):
        self.reads += 1
        key = lambda x: tuple(map(int, x.split("-")))  # noqa: E731
        return copy.deepcopy([e for e in self.entries if key(e["id"]) > key(last_id)][:count])


SEMIO_NOTE = """Handover received through the coordination stream. It is addressed to you alone; your teammate is not working on this.

kind: handover
from: {sender}
artifact: {artifact}
summary: {summary}

Their task statement is at /workspace/handover/peer-task.md and their finished change is the patch
/workspace/handover/peer.patch. Bring it into your workspace so one tree holds both features.
{detail}
Their tests: $ {peer_check}
Your tests:  $ {own_check}
When both pass, reply WITHOUT a tool call and give a short factual handover."""


def run_semio(ledger: Ledger, model: Model, sides: list, scope: str, env_dir: Path, out: Path, pair: dict) -> dict:
    """Finished work travels as typed handovers. Software merges; a worker is woken only when it must act."""
    transport = MemoryTransport()
    commit = sides[0]["task"]["commit"]
    identity = dict(protocol="klp-core/v0.3", mission_id="pair-" + hashlib.sha256(pair["id"].encode()).hexdigest()[:16],
                    mission_revision=1, mission_hash=hashlib.sha256((sides[0]["statement"] + sides[1]["statement"]).encode()).hexdigest(),
                    task_id="integrate", contract_id="one-tree-both-features", contract_revision=1, artifact_revision=commit)
    names = {s["name"]: f"worker-{s['name']}" for s in sides}
    coordinator = SemioAdapter(transport, str(out / "coordinator.sqlite"), identity=identity, agent="coordinator",
                               allowed_senders=set(names.values()), allowed_recipients=set(names.values()))
    workers = {s["name"]: SemioAdapter(transport, str(out / f"worker-{s['name']}.sqlite"), identity=identity,
                                       agent=names[s["name"]], allowed_senders={"coordinator"}, allowed_recipients={"coordinator"})
               for s in sides}
    serial = [0]

    def envelope(sender: str, to: str, unit: str, summary: str, refs: list, reply_to: str | None = None) -> dict:
        serial[0] += 1
        return dict(identity, message_id=f"{identity['mission_id']}-{serial[0]}", unit_id=unit, kind="handover",
                    correlation_id=identity["mission_id"], in_reply_to=reply_to, capability_report_ref=None,
                    affected_capabilities=[], evidence_refs=refs, summary=summary,
                    timestamp=datetime.now(timezone.utc).isoformat(), **{"from": sender, "to": to})

    try:
        for s in sides:  # each worker reports its finished feature once
            digest = hashlib.sha256(s["patch"]).hexdigest()
            workers[s["name"]].publish(envelope(names[s["name"]], "coordinator", f"feature-{s['name']}",
                                                f"{s['title']}: complete, declared checks pass.",
                                                [f"snapshot:{s['final']}", f"patch-sha256:{digest}"]))
        received = coordinator.poll()
        for message in received:
            coordinator.mark_delivered(message["message_id"])
        by_sender = {m["from"]: m for m in received}
        first, second = sides  # receipt order: the later arrival integrates onto the earlier artifact
        merge = try_merge(env_dir, out / "merge", first["patch"], second["patch"], commit)
        result = dict(sessions_woken=0, messages=len(transport.entries), merge_clean=merge["clean"], steps={},
                      double_integration=False, transport_reads=transport.reads)
        if merge["clean"]:
            checks = visible_checks(merge["sandbox"], sides)
            if all(c["passed"] for c in checks):
                return dict(result, patch=merge["patch"], checks=checks, messages=len(transport.entries),
                            transport_reads=transport.reads)
            detail = "The two changes merge without conflict, but these tests fail on the merged tree:\n" + "\n".join(
                clip(c["output"], 1500) for c in checks if not c["passed"])
        else:
            detail = ("git cannot merge the two changes on its own. Conflicting files: "
                      + (", ".join(merge["conflict_files"]) or "see the patch") + ".")
        shutil.rmtree(out / "merge", ignore_errors=True)
        integrator, peer = second, first
        notice = envelope("coordinator", names[integrator["name"]], "integration",
                          f"Integrate {peer['title']} into your tree.",
                          [by_sender[names[peer["name"]]]["evidence_refs"][0], "file:/workspace/handover/peer.patch"],
                          by_sender[names[peer["name"]]]["message_id"])
        coordinator.publish(notice)
        inbox = workers[integrator["name"]].poll()
        workers[peer["name"]].poll()  # the peer's inbox stays empty: it is not addressed, so it is not woken
        if [m["message_id"] for m in inbox] != [notice["message_id"]]:
            raise RuntimeError("integration handover was not delivered exactly once")
        workers[integrator["name"]].mark_delivered(notice["message_id"])
        integrator["sandbox"].write_file("/workspace/handover/peer.patch", peer["patch"].decode("utf-8", "replace"))
        integrator["sandbox"].write_file("/workspace/handover/peer-task.md", peer["statement"])
        prompt = SEMIO_NOTE.format(sender=names[peer["name"]], artifact=notice["evidence_refs"][0], summary=notice["summary"],
                                   detail=detail, peer_check=peer["check"], own_check=integrator["check"])
        session = run_worker(ledger, model, integrator["sandbox"], prompt, scope=scope, max_steps=INTEGRATE_STEPS,
                             command_timeout=300, messages=integrator["messages"], role="integrate")
        workers[integrator["name"]].publish(envelope(names[integrator["name"]], "coordinator", "integration",
                                                     "Integrated tree ready.", [f"snapshot-of:{integrator['name']}"],
                                                     notice["message_id"]))
        for message in coordinator.poll():
            coordinator.mark_delivered(message["message_id"])
        return dict(result, sessions_woken=1, integrator=integrator, session=session, steps={integrator["name"]: session["steps"]},
                    messages=len(transport.entries), transport_reads=transport.reads)
    finally:
        coordinator.close()
        for adapter in workers.values():
            adapter.close()


# ---------------------------------------------------------------- one pair, one arm

REPAIR_NOTE = "The runner ran both test commands on your integrated tree and these failed. Fix them, re-run both, then give your handover.\n\n{output}"


def finish_integration(ledger: Ledger, model: Model, sides: list, integrator: dict, history: list, scope: str,
                       role: str) -> tuple[bytes, list, int]:
    """Runner-executed checks on the integrated tree, one bounded repair if they fail, then the final patch."""
    checks, extra = visible_checks(integrator["sandbox"], sides), 0
    if not all(c["passed"] for c in checks):
        failing = "\n\n".join(f"$ {c['command']}\n{clip(c['output'], 2500)}" for c in checks if not c["passed"])
        session = run_worker(ledger, model, integrator["sandbox"], REPAIR_NOTE.format(output=failing), scope=scope,
                             max_steps=INTEGRATE_STEPS, command_timeout=300, messages=history, role=role)
        extra, checks = session["steps"], visible_checks(integrator["sandbox"], sides)
    revision = integrator["snapshots"].take("integrated")
    return integrator["snapshots"].patch(integrator["base"], revision), checks, extra


def run_one(work: Path, ledger: Ledger, pair: dict, arm: str, tasks: dict) -> dict:
    out = work / "pair-runs" / arm / pair["id"]
    if (out / "result.json").exists():
        return json.loads((out / "result.json").read_text())
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    task_a, task_b = tasks[pair["a"]], tasks[pair["b"]]
    env_dir, scope, started = work / "envs" / task_a["env"], f"pair-{arm}/{pair['id']}", time.time()
    worker = Model.from_spec(MODELS["worker"])
    info: dict = dict(sessions_woken=0, messages=0, double_integration=False, steps={})
    patch, checks, state = None, [], "completed"
    try:
        if arm == "solo":
            ws = fresh_workspace(env_dir, out / "ws")
            check_a, check_b = (f"{PYTEST} -x {' '.join(t['test_files'])}" for t in (task_a, task_b))
            prompt = ("Implement BOTH of the following features in this repository, in one tree.\n\n# Feature 1\n"
                      + Path(task_a["statement"]).read_text().strip() + "\n\n# Feature 2\n"
                      + Path(task_b["statement"]).read_text().strip()
                      + "\n\nExisting tests that must keep passing:\n" + "\n".join(f"$ {c}" for c in dict.fromkeys((check_a, check_b))))
            receipt = run_standard(ledger=ledger, worker=Model.from_spec(MODELS["frontier"]), critic=None, sandbox=box(ws, env_dir),
                                   task=prompt, checks=list(dict.fromkeys((check_a, check_b))), scope=scope, limits=Limits(),
                                   out_dir=out, task_id=pair["id"], project_revision=task_a["commit"])
            patch = Snapshots(box(ws, env_dir), out / "snapshots").patch(receipt["base_revision"], receipt["completion"]["final_revision"])
            info.update(sessions_woken=1, steps={"solo": sum(s["calls"] for s in ledger.summary(scope=scope).values())})
        else:
            sides = [side(work, out, task_a, "a"), side(work, out, task_b, "b")]
            if arm == "merge":
                merge = try_merge(env_dir, out / "merge", sides[0]["patch"], sides[1]["patch"], task_a["commit"])
                patch, state = merge["patch"], "completed" if merge["clean"] else "merge_conflict"
                info["merge_clean"] = merge["clean"]
            elif arm == "chat":
                chat = run_chat(ledger, worker, sides, scope)
                info.update({k: chat[k] for k in ("sessions_woken", "messages", "double_integration", "steps")})
                if chat["integrator"]:
                    me = chat["integrator"]
                    patch, checks, extra = finish_integration(ledger, worker, sides, me["side"], me["history"], scope, "chat")
                    info["steps"][me["side"]["name"]] += extra
                else:
                    state = "no_integration"
            elif arm == "semio":
                semio = run_semio(ledger, worker, sides, scope, env_dir, out, pair)
                info.update({k: semio[k] for k in ("sessions_woken", "messages", "double_integration", "steps", "merge_clean",
                                                   "transport_reads")})
                if semio.get("patch") is not None:
                    patch, checks = semio["patch"], semio["checks"]
                else:
                    me = semio["integrator"]
                    patch, checks, extra = finish_integration(ledger, worker, sides, me, semio["session"]["messages"], scope,
                                                              "integrate")
                    info["steps"][me["name"]] += extra
    except BudgetExceeded as error:
        state, info["error"] = "budget_exhausted", str(error)
    except ProviderError as error:
        state, info["error"] = "blocked", str(error)[:300]
    except Exception as error:  # a harness fault is a recorded failure, never a silent skip
        state, info["error"] = "harness_error", f"{type(error).__name__}: {error}"[:400]
    grades = grade(work, out, [task_a, task_b], patch) if state not in ("blocked", "harness_error") else {}
    effort = ledger.summary(scope=scope)
    result = dict(pair=pair["id"], arm=arm, state=state, solved=bool(grades) and all(g["passed"] for g in grades.values()),
                  features_passing=sum(bool(g["passed"]) for g in grades.values()),
                  grades={k: dict(passed=g["passed"], stage=g["stage"]) for k, g in grades.items()},
                  checks_passed=bool(checks) and all(c["passed"] for c in checks), usd=str(ledger.spent(scope=scope)),
                  model_calls=sum(s["calls"] for s in effort.values()), effort=effort, seconds=round(time.time() - started, 1),
                  **{k: v for k, v in info.items()})
    for name in ("ws", "ws-a", "ws-b", "snapshots", "snapshots-a", "snapshots-b", "merge", "grade"):
        shutil.rmtree(out / name, ignore_errors=True)  # results and the ledger are the record
    (out / "result.json").write_text(json.dumps(result, indent=1))
    return result


def run(work: Path, arms: list[str], cap: float, jobs: int, limit: int | None) -> None:
    tasks = {t["id"]: t for t in json.loads((work / "tasks.json").read_text())["tasks"]}
    pairs = json.loads((work / "pairs.json").read_text())["pairs"][:limit]
    ledger = Ledger(work / "pairs-ledger.jsonl", cap)
    before = ledger.spent()
    ledger.cap += before
    print(f"{len(pairs)} pairs x {len(arms)} arms, cap ${cap}, ledger so far ${before:.4f}", flush=True)
    with concurrent.futures.ThreadPoolExecutor(jobs) as pool:
        futures = [pool.submit(run_one, work, ledger, p, a, tasks) for a in arms for p in pairs]
        for future in concurrent.futures.as_completed(futures):
            r = future.result()
            print(f"  {r['arm']:6s} {r['pair']:34s} {r['state']:15s} solved={r['solved']!s:5s} calls={r['model_calls']:3d} "
                  f"woken={r.get('sessions_woken')} msgs={r.get('messages')} ${float(r['usd']):.4f} run=${ledger.spent() - before:.3f}",
                  flush=True)
    report(work)


def report(work: Path) -> dict:
    rows = [json.loads(p.read_text()) for p in sorted((work / "pair-runs").glob("*/*/result.json"))]
    pairs = {p["id"]: p for p in json.loads((work / "pairs.json").read_text())["pairs"]}
    by_arm: dict = {}
    for r in rows:
        if r["pair"] in pairs:
            by_arm.setdefault(r["arm"], {})[r["pair"]] = r
    common = sorted(set.intersection(*[set(v) for v in by_arm.values()])) if by_arm else []
    built = {}
    for arm in BUILDER_ARMS:  # what it cost to build and review the two features of each pair
        for file in (work / "runs" / arm).glob("*/result.json"):
            r = json.loads(file.read_text())
            built[r["task"]] = built.get(r["task"], D(0)) + D(r["usd"])
    table = {}
    for arm in [a for a in ARMS if a in by_arm]:
        items = [by_arm[arm][p] for p in common]
        own = sum((D(r["usd"]) for r in items), D(0))
        features = D(0) if arm == "solo" else sum((built.get(pairs[p]["a"], D(0)) + built.get(pairs[p]["b"], D(0)) for p in common), D(0))
        solved = sum(bool(r["solved"]) for r in items)
        table[ARMS[arm]] = dict(
            arm=arm, pairs=len(items), solved=solved, integration_usd=str(own), features_usd=str(features),
            usd=str(own + features), usd_per_pair=str((own + features) / len(items)) if items else None,
            usd_per_solved_pair=str((own + features) / solved) if solved else None,
            model_calls=sum(r["model_calls"] for r in items), sessions_woken=sum(r.get("sessions_woken") or 0 for r in items),
            messages=sum(r.get("messages") or 0 for r in items),
            pairs_without_a_model_call=sum(r["model_calls"] == 0 for r in items),
            double_integrations=sum(bool(r.get("double_integration")) for r in items),
            input_tokens=sum(s["input"] for r in items for s in r["effort"].values()),
            output_tokens=sum(s["output"] for r in items for s in r["effort"].values()),
            median_seconds=statistics.median(r["seconds"] for r in items) if items else None,
            states=dict(sorted({s: sum(r["state"] == s for r in items) for s in {r["state"] for r in items}}.items())))
    out = dict(pairs_compared=len(common), source_arm=SOURCE_ARM, arms=table)
    (work / "pairs-report.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("select", "run", "report"))
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--pairs", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20261110)
    parser.add_argument("--arms", default="merge,chat,semio")
    parser.add_argument("--cap", type=float, default=5.0)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.command == "select":
        select(args.work, args.pairs, args.seed)
    elif args.command == "run":
        run(args.work, args.arms.split(","), args.cap, args.jobs, args.limit)
    else:
        report(args.work)


if __name__ == "__main__":
    main()
