"""Offline tests for the feature benchmark's bookkeeping. No network, no models."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bench import features  # noqa: E402


def result(task, arm, *, solved, first, worker, critic=None, repair=None, reviews=(), repairs=()):
    effort = {"worker": {"usd": worker}}
    if critic:
        effort["critic"] = {"usd": critic}
    if repair:
        effort["repair"] = {"usd": repair}
    total = sum(float(v["usd"]) for v in effort.values())
    return dict(task=task, arm=arm, state="completed", solved=solved, first_candidate_solved=first,
                usd=f"{total:.4f}", seconds=10, effort=effort, reviews=list(reviews), repairs=list(repairs))


class Report(unittest.TestCase):
    def write(self, rows):
        work = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        for row in rows:
            folder = work / "runs" / row["arm"] / row["task"]
            folder.mkdir(parents=True)
            (folder / "result.json").write_text(json.dumps(row))
        return work

    def test_review_arm_reuses_worker_candidates_and_carries_their_cost(self):
        work = self.write([
            result("t1", "frontier-solo", solved=True, first=True, worker="0.4000"),
            result("t2", "frontier-solo", solved=False, first=False, worker="0.6000"),
            result("t1", "worker", solved=True, first=True, worker="0.0200"),
            result("t2", "worker", solved=False, first=False, worker="0.0300"),
            result("t3", "worker", solved=True, first=True, worker="0.0100"),  # not in every arm: left out
            dict(result("t1", "klp-sol", solved=True, first=True, worker="0", critic="0.0300",
                        reviews=[dict(verdict="PASS", packet_bytes=1, dispositions=[])]), effort={"critic": {"usd": "0.0300"}}, usd="0.0300"),
            dict(result("t2", "klp-sol", solved=True, first=False, worker="0", critic="0.0600", repair="0.0100",
                        reviews=[dict(verdict="FAIL", packet_bytes=1, dispositions=["confirmed", "refuted"]),
                                 dict(verdict="PASS", packet_bytes=1, dispositions=[])],
                        repairs=[dict(kept=True, closed=1, probes=1)]),
                 effort={"critic": {"usd": "0.0600"}, "repair": {"usd": "0.0100"}}, usd="0.0700"),
        ])
        report = features.report(work)
        self.assertEqual(report["tasks_compared"], 2)
        rows = {v["arm"]: v for v in report["arms"].values()}
        self.assertEqual((rows["frontier-solo"]["solved"], rows["frontier-solo"]["usd"]), (1, "1.0000"))
        self.assertEqual((rows["worker"]["solved"], rows["worker"]["usd"]), (1, "0.0500"))
        # review arm = its own critic and repair spend plus the worker spend it built on
        self.assertEqual((rows["klp-sol"]["solved"], rows["klp-sol"]["usd"]), (2, "0.1500"))
        self.assertEqual(rows["klp-sol"]["usd_per_solved"], "0.0750")
        review = report["reviews"]["klp-sol"]
        self.assertEqual(review["fixed_by_review"], ["t2"])
        self.assertEqual(review["broken_by_review"], [])
        self.assertEqual((review["findings"]["confirmed"], review["findings"]["refuted"], review["findings_closed"]), (1, 1, 1))
        self.assertEqual(review["usd_by_role"], {"worker": "0.0500", "critic": "0.0900", "repair": "0.0100"})

    def test_report_can_be_limited_to_named_arms(self):
        work = self.write([result("t1", "frontier-solo", solved=True, first=True, worker="0.4000"),
                           result("t1", "worker", solved=True, first=True, worker="0.0200"),
                           result("t2", "worker", solved=True, first=True, worker="0.0200")])
        self.assertEqual(features.report(work)["tasks_compared"], 1)
        self.assertEqual(features.report(work, ["worker"])["tasks_compared"], 2)


class TaskFolder(unittest.TestCase):
    def test_reads_repository_commit_python_and_test_files(self):
        folder = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        (folder / "Dockerfile").write_text(
            "FROM python:3.11-slim\nRUN git clone https://github.com/pallets/click.git repo && \\\n"
            "    cd repo && \\\n    git checkout d8763b93021c416549b5f8b4b5497234619410db\n")
        (folder / "runner.sh").write_text("python -m pytest tests/test_a.py tests/test_b.py -v\n")
        spec = features.read_task_folder(folder)
        self.assertEqual(spec, dict(url="https://github.com/pallets/click", python="3.11",
                                    commit="d8763b93021c416549b5f8b4b5497234619410db",
                                    test_files=["tests/test_a.py", "tests/test_b.py"]))


if __name__ == "__main__":
    unittest.main()
