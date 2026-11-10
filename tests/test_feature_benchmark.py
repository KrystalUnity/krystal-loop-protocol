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
    def test_report_pairs_arms_and_separates_review_cost(self):
        work = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        rows = [
            result("t1", "frontier-solo", solved=True, first=True, worker="0.4000"),
            result("t2", "frontier-solo", solved=False, first=False, worker="0.6000"),
            result("t1", "klp", solved=True, first=True, worker="0.0200", critic="0.0300",
                   reviews=[dict(verdict="PASS", packet_bytes=1, dispositions=[])]),
            result("t2", "klp", solved=True, first=False, worker="0.0300", critic="0.0600", repair="0.0100",
                   reviews=[dict(verdict="FAIL", packet_bytes=1, dispositions=["confirmed", "refuted"]),
                            dict(verdict="PASS", packet_bytes=1, dispositions=[])],
                   repairs=[dict(kept=True, closed=1, probes=1)]),
            result("t3", "klp", solved=True, first=True, worker="0.0100", critic="0.0100"),  # no frontier pair
        ]
        for row in rows:
            folder = work / "runs" / row["arm"] / row["task"]
            folder.mkdir(parents=True)
            (folder / "result.json").write_text(json.dumps(row))
        report = features.report(work)
        self.assertEqual(report["tasks_compared"], 2)
        arms = report["arms"]
        self.assertEqual((arms["frontier model alone"]["solved"], arms["frontier model alone"]["usd"]), (1, "1.0000"))
        self.assertEqual((arms["low-cost worker alone"]["solved"], arms["low-cost worker alone"]["usd"]), (1, "0.0500"))
        self.assertEqual((arms["KLP Standard"]["solved"], arms["KLP Standard"]["usd"]), (2, "0.1500"))
        self.assertEqual(arms["KLP Standard"]["usd_per_solved"], "0.0750")
        review = report["klp_review"]
        self.assertEqual(review["fixed_by_review"], ["t2"])
        self.assertEqual(review["broken_by_review"], [])
        self.assertEqual(review["findings"]["confirmed"], 1)
        self.assertEqual(review["findings"]["refuted"], 1)
        self.assertEqual(review["usd_by_role"], {"worker": "0.0500", "critic": "0.0900", "repair": "0.0100"})


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
