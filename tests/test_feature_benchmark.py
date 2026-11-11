"""Offline tests for the feature benchmark's bookkeeping. No network, no models."""
from __future__ import annotations

import json
import subprocess
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


class GradeYourOwn(unittest.TestCase):
    """Grading patches made outside the harness. Real Git; the hidden-test run itself needs a prepared benchmark."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        self.work, self.source = self.root / "work", self.root / "mine"
        origin = self.work / "envs" / "env1" / "ws" / "repo"
        origin.mkdir(parents=True)
        self.git(origin, "init", "-q")
        (origin / "app.py").write_text("def greet():\n    return 'hello'\n")
        (origin / ".gitignore").write_text("__pycache__/\n")
        self.git(origin, "add", "-A")
        self.git(origin, "commit", "-q", "-m", "base")
        commit = self.git(origin, "rev-parse", "HEAD").strip()
        statement = self.root / "feature.md"
        statement.write_text("Add a farewell function.\n")
        task = dict(env="env1", commit=commit, test_files=["tests/test_app.py"], statement=str(statement), valid=True)
        (self.work / "tasks.json").write_text(json.dumps(dict(tasks=[
            dict(task, id="t-edited"), dict(task, id="t-committed"), dict(task, id="t-file"), dict(task, id="t-untouched"),
            dict(task, id="t-absent"), dict(task, id="t-invalid", valid=False)])))

    def git(self, repo, *args):
        return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@localhost", "-C", str(repo), *args],
                              check=True, capture_output=True, text=True).stdout

    def test_handout_then_grade_collects_every_kind_of_work(self):
        features.handout(self.work, self.source, ["t-edited", "t-committed", "t-file", "t-untouched"])
        self.assertEqual((self.source / "t-edited" / "TASK.md").read_text(),
                         "Add a farewell function.\n\nExisting tests that must keep passing:\n"
                         "$ python -m pytest -q -p no:cacheprovider -x tests/test_app.py\n")
        edited = self.source / "t-edited" / "repo"
        (edited / "app.py").write_text("def greet():\n    return 'hello'\n\ndef farewell():\n    return 'bye'\n")
        (edited / "notes.txt").write_text("a new file\n")                      # untracked files are part of the work
        (edited / "__pycache__").mkdir()
        (edited / "__pycache__" / "app.pyc").write_text("ignored")              # ignored files are not
        committed = self.source / "t-committed" / "repo"
        (committed / "app.py").write_text("def greet():\n    return 'hi'\n")
        self.git(committed, "commit", "-q", "-am", "the tool committed its work")
        before = self.git(edited, "status", "--porcelain")
        pristine = self.work / "envs" / "env1" / "ws" / "repo"
        # a tool that plants a filter in its checkout's own Git config must not get it run on the host
        marker = self.root / "filter-ran"
        self.git(edited, "config", "filter.planted.clean", f"sh -c 'touch {marker}; cat'")
        (edited / ".gitattributes").write_text("* filter=planted\n")
        (self.source / "t-file.patch").write_bytes(
            features.workspace_patch(edited, self.git(edited, "rev-parse", "HEAD").strip(), pristine))
        self.assertFalse(marker.exists())
        features.handout(self.work, self.source, ["t-edited"])                    # a second handout keeps the work
        self.assertIn("farewell", (edited / "app.py").read_text())

        seen = {}

        def grader(env_dir, scratch, task, candidate=None):
            seen[task["id"]] = candidate.decode()
            return dict(passed="farewell" in seen[task["id"]], stage="tests", output="1 failed")

        summary = features.grade(self.work, self.source, "my-setup", 2, None, 2.5, grader=grader)
        self.assertFalse(marker.exists())
        (edited / ".gitattributes").unlink()
        self.git(edited, "config", "--unset", "filter.planted.clean")
        self.assertEqual(self.git(edited, "status", "--porcelain"), before)      # grading leaves the checkout alone
        self.assertIn("+def farewell():", seen["t-edited"])
        self.assertIn("notes.txt", seen["t-edited"])
        self.assertNotIn("__pycache__", seen["t-edited"])
        self.assertIn("+    return 'hi'", seen["t-committed"])
        self.assertEqual(seen["t-file"], seen["t-edited"])
        rows = {r["task"]: r for r in summary["results"]}
        self.assertEqual({k: (v["solved"], v["stage"]) for k, v in rows.items()}, {
            "t-edited": (True, "tests"), "t-committed": (False, "tests"), "t-file": (True, "tests"),
            "t-untouched": (False, "no patch"), "t-absent": (False, "no patch")})   # the invalid task is never graded
        self.assertEqual((summary["tasks"], summary["patches"], summary["solved"]), (5, 3, 2))
        self.assertEqual(summary["usd_per_task_self_reported"], "0.5000")
        self.assertEqual(json.loads((self.work / "external" / "my-setup" / "results.json").read_text()), summary)

    def test_name_cannot_leave_the_results_folder(self):
        with self.assertRaises(SystemExit):
            features.grade(self.work, self.source, "../elsewhere", 1, None, None, grader=None)


if __name__ == "__main__":
    unittest.main()
