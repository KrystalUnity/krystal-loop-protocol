"""Offline tests for the paired-feature benchmark: pair selection and the Semio handover path. No models."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench import pairs  # noqa: E402


class PairSelection(unittest.TestCase):
    def test_pairs_are_conflicting_solved_and_spread_over_base_commits(self):
        work = Path(tempfile.mkdtemp(prefix="klp-pairs-"))
        dataset = work / "CooperBench" / "dataset"
        tasks = []
        for repo, number in (("pallets_click", 1), ("pallets_jinja", 2)):
            for feature in range(1, 5):
                folder = dataset / f"{repo}_task" / f"task{number}" / f"feature{feature}"
                folder.mkdir(parents=True)
                (folder / "feature.md").write_text("**Title**: x")
                task = f"{repo}-task{number}-feature{feature}"
                tasks.append(dict(id=task, valid=True, statement=str(folder / "feature.md")))
                run = work / "runs" / pairs.SOURCE_ARM / task
                run.mkdir(parents=True)
                (run / "result.json").write_text(json.dumps(dict(task=task, solved=feature != 4)))
        (work / "tasks.json").write_text(json.dumps(dict(tasks=tasks)))
        gold = [dict(repo=f"{repo}_task", task_id=number, f1=a, f2=b)
                for repo, number in (("pallets_click", 1), ("pallets_jinja", 2)) for a, b in ((1, 2), (1, 3), (2, 4))]
        (dataset / "gold_conflict_report.json").write_text(json.dumps(dict(conflict_pairs=gold)))
        pairs.select(work, 3, seed=1)
        chosen = json.loads((work / "pairs.json").read_text())
        self.assertEqual(chosen["eligible"], 4)  # the pairs with feature 4, which was not solved, are out
        self.assertEqual(len(chosen["pairs"]), 3)
        self.assertEqual({p["id"].rsplit("-", 1)[0] for p in chosen["pairs"]}, {"pallets_click-task1", "pallets_jinja-task2"})
        self.assertTrue(all("feature4" not in p["a"] + p["b"] for p in chosen["pairs"]))


class SemioHandover(unittest.TestCase):
    def test_a_handover_reaches_its_one_recipient_once_and_nobody_else(self):
        folder = Path(tempfile.mkdtemp(prefix="klp-semio-"))
        transport = pairs.MemoryTransport()
        identity = dict(protocol="klp-core/v0.3", mission_id="pair-1", mission_revision=1, mission_hash="0" * 64,
                        task_id="integrate", contract_id="one-tree", contract_revision=1, artifact_revision="abc")
        coordinator = pairs.SemioAdapter(transport, str(folder / "c.sqlite"), identity=identity, agent="coordinator",
                                         allowed_senders={"worker-a", "worker-b"}, allowed_recipients={"worker-a", "worker-b"})
        a, b = (pairs.SemioAdapter(transport, str(folder / f"{n}.sqlite"), identity=identity, agent=n,
                                   allowed_senders={"coordinator"}, allowed_recipients={"coordinator"})
                for n in ("worker-a", "worker-b"))
        notice = dict(identity, message_id="m1", unit_id="integration", kind="handover", correlation_id="pair-1",
                      in_reply_to=None, capability_report_ref=None, affected_capabilities=[],
                      evidence_refs=["snapshot:abc"], summary="Integrate the peer artifact.",
                      timestamp=datetime.now(timezone.utc).isoformat(), **{"from": "coordinator", "to": "worker-b"})
        coordinator.publish(notice)
        coordinator.publish(notice)  # the same notice sent twice is still one delivery
        self.assertEqual([m["message_id"] for m in b.poll()], ["m1"])
        self.assertEqual(a.poll(), [])
        b.mark_delivered("m1")
        self.assertEqual(b.poll(), [])
        for adapter in (coordinator, a, b):
            adapter.close()


if __name__ == "__main__":
    unittest.main()
