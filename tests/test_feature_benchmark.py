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


class TaskSize(unittest.TestCase):
    def test_counts_hunk_lines_files_and_new_tests_but_not_headers(self):
        diff = ("diff --git a/src/a.py b/src/a.py\nindex 1..2 100644\n--- a/src/a.py\n+++ b/src/a.py\n"
                "@@ -1,2 +1,3 @@\n context\n-old\n+new\n++x = 1\n"
                "diff --git a/tests/test_a.py b/tests/test_a.py\n--- /dev/null\n+++ b/tests/test_a.py\n"
                "@@ -0,0 +1,4 @@\n+def test_one():\n+    pass\n+async def test_two():\n+    pass\n")
        self.assertEqual(features.patch_size(diff), dict(files=2, added=6, removed=1, tests_added=2))


class Probes(unittest.TestCase):
    @staticmethod
    def finding(fid, file, disposition="confirmed", **extra):
        return dict(id=fid, claim=fid, disposition=disposition,
                    probe=dict(file=f"/workspace/probes/{file}", command="python -m pytest -q /workspace/probes/" + file,
                               returncode=1, timed_out=False), **extra)

    def test_a_reused_file_name_keeps_only_the_last_probe_and_acceptance_findings_share_one_file(self):
        from bench import probes
        receipt = dict(reviews=[
            dict(reviewed_revision="r1", findings=[self.finding("F1", "test_f1.py"), self.finding("F2", "test_f2.py"),
                                                   self.finding("A1", "test_acceptance.py", source="acceptance"),
                                                   self.finding("A2", "test_acceptance.py", source="acceptance")]),
            dict(reviewed_revision="r2", findings=[self.finding("R2-F1", "test_f1.py"),
                                                   dict(self.finding("F2", "test_f2.py"), carried=True)]),
        ])
        kept = {(row["review"], row["finding"]["id"]): row["retained"] for row in probes.probed_findings(receipt)}
        self.assertEqual(kept, {(1, "F1"): False, (1, "F2"): True, (1, "A1"): True, (1, "A2"): True, (2, "R2-F1"): True})

    def test_retention_follows_each_write_not_the_finding_ids(self):
        from bench import probes
        failed = dict(self.finding("F2", "test_a.py"))
        failed["probe"] = dict(failed["probe"], returncode=None, timed_out=True,
                               output="could not write /workspace/probes/test_a.py in the sandbox: no space")
        receipts = {
            "an acceptance file with no failing test still replaces a probe of the same name": dict(reviews=[dict(
                reviewed_revision="r1", findings=[self.finding("F1", "test_acceptance.py")],
                acceptance=dict(file="/workspace/probes/test_acceptance.py", result="passed"))]),
            "two findings with the same id keep only the later write": dict(reviews=[dict(
                reviewed_revision="r1", findings=[self.finding("F2", "test_a.py"), self.finding("F2", "test_a.py")])]),
            "a probe that could not be written owns nothing and spoils the earlier file": dict(reviews=[dict(
                reviewed_revision="r1", findings=[self.finding("F1", "test_a.py"), failed])]),
        }
        expected = {"an acceptance file with no failing test still replaces a probe of the same name": [False],
                    "two findings with the same id keep only the later write": [False, True],
                    "a probe that could not be written owns nothing and spoils the earlier file": [False, False]}
        for title, receipt in receipts.items():
            with self.subTest(title):
                self.assertEqual([row["retained"] for row in probes.probed_findings(receipt)], expected[title])

    def test_a_probe_is_read_only_as_a_small_regular_file_reached_without_a_link(self):
        import os
        from bench import probes
        root = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        secret = root / "host-secret.txt"
        secret.write_text("not for the pack")
        ws = root / "ws"
        (ws / "probes").mkdir(parents=True)
        (ws / "probes" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
        (ws / "probes" / "test_link.py").symlink_to(secret)
        os.mkfifo(ws / "probes" / "test_fifo.py")
        (ws / "probes" / "test_big.py").write_bytes(b"#" * (probes.PROBE_MAX_BYTES + 1))
        (ws / "probes" / "test_bytes.py").write_bytes(b"\xff\xfe")
        self.assertEqual(probes.read_probe(ws, "test_ok.py"), "def test_ok():\n    assert True\n")
        for name in ("test_link.py", "test_fifo.py", "test_big.py", "test_bytes.py", "missing.py", "..", "../ws"):
            with self.subTest(name):
                self.assertIsNone(probes.read_probe(ws, name))
        linked = root / "linked-ws"
        linked.mkdir()
        (linked / "probes").symlink_to(ws / "probes")
        self.assertIsNone(probes.read_probe(linked, "test_ok.py"))

    def test_names_from_a_published_pack_never_leave_the_scratch_folder(self):
        from bench import probes
        self.assertEqual(probes.probe_name("/workspace/probes/test_f1.py"), "test_f1.py")
        for unsafe in ("..", ".", "", "/workspace/probes/..", "a b.py", "t" * 253 + ".py"):
            self.assertIsNone(probes.probe_name(unsafe))
        work = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        first, second = probes.scratch_root(work, "probes-reference"), probes.scratch_root(work, "probes-reference")
        self.assertNotEqual(first, second)  # two runs at once never share a folder
        self.assertEqual(probes.scratch_dir(first, 7), first / "7")
        for index in ("../../..", "", "7/../.."):
            with self.assertRaises(ValueError):
                probes.scratch_dir(first, index)

    def test_reference_builds_no_path_from_a_published_pack(self):
        from bench import probes
        work = Path(tempfile.mkdtemp(prefix="klp-bench-test-"))
        victim = work.parent / (work.name + "-victim")
        victim.mkdir()
        (work / "tasks.json").write_text(json.dumps(dict(tasks=[dict(
            id="t1", valid=True, env="t1-env", gold_patch=str(work / "feature.patch"))])))
        row = lambda **over: dict(dict(arm="klp-3", task="t1", review=1, id="F1", reference=dict(outcome="agrees"),
                                       probe=dict(file="test_f1.py", content="", command="true")), **over)
        pack = work / "probes.json"
        pack.write_text(json.dumps(dict(findings=[
            row(review=str(victim.parent / work.name)), row(arm="../../..", id="victim"), row(id="../../x"),
            row(probe=dict(file="..", content="", command="true"))])))
        seen = []

        def fake_run_probe(env_dir, ws, file, content, command, **patch):
            seen.append(ws)
            return dict(stage="probe", returncode=0, timed_out=False, output="")

        original, probes.run_probe = probes.run_probe, fake_run_probe
        try:
            self.assertEqual(probes.reference(work, pack, jobs=4), 0)
        finally:
            probes.run_probe = original
        self.assertEqual(len(seen), 4)
        for ws in seen:
            self.assertTrue(ws.resolve().is_relative_to((work / "scratch").resolve()), ws)
        self.assertTrue(victim.is_dir())
        self.assertEqual(list((work / "scratch").iterdir()), [])  # only its own scratch, and it is gone
        for bad in (dict(findings=[row(task="not-in-this-folder")]), dict(findings={}), dict(findings=[]), []):
            pack.write_text(json.dumps(bad))
            with self.assertRaises(SystemExit):
                probes.reference(work, pack, jobs=1)

    def test_outcome_on_the_reference(self):
        from bench import probes
        run = lambda rc, output="", stage="probe", timed_out=False: dict(stage=stage, returncode=rc, timed_out=timed_out,
                                                                         output=output)
        command = "python -m pytest -q /workspace/probes/test_f1.py"
        self.assertEqual(probes.outcome(run(0), command)[0], "agrees")
        self.assertEqual(probes.outcome(run(1, "E   AssertionError: still running\nFAILED x::t"), command),
                         ("asks_more", "AssertionError: still running"))
        for output in ("E   ImportError: cannot import name 'helper'", "E   AttributeError: 'Context' object has no attribute '_x'",
                       "E   TypeError: edit() got an unexpected keyword argument 'wait'"):
            self.assertEqual(probes.outcome(run(1, output), command)[0], "inconclusive")
        self.assertEqual(probes.outcome(run(2, "ERROR collecting"), command)[0], "inconclusive")
        self.assertEqual(probes.outcome(run(None, timed_out=True), command)[0], "inconclusive")
        self.assertEqual(probes.outcome(run(None, stage="apply"), command)[0], "inconclusive")
        self.assertTrue(probes.reproduced(dict(returncode=1, timed_out=False), run(1)))
        self.assertFalse(probes.reproduced(dict(returncode=1, timed_out=False), run(0)))
        self.assertFalse(probes.reproduced(dict(returncode=1, timed_out=False), run(None, stage="apply")))


class Statistics(unittest.TestCase):
    def setUp(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "case-studies" / "feature-benchmark-2026-11-10"))
        import analysis
        self.analysis = analysis

    def test_wilson_matches_published_values(self):
        for (k, n), expected in {(5, 10): (0.2366, 0.7634), (0, 10): (0.0, 0.2775), (81, 263): (0.2553, 0.3662)}.items():
            low, high = self.analysis.wilson(k, n)
            self.assertAlmostEqual(low, expected[0], places=4)
            self.assertAlmostEqual(high, expected[1], places=4)

    def test_exact_mcnemar_and_the_split_a_gap_needs(self):
        self.assertEqual(self.analysis.mcnemar(5, 2), 58 / 128)
        self.assertEqual(self.analysis.mcnemar(6, 0), 2 / 64)
        self.assertEqual(self.analysis.mcnemar(5, 0), 2 / 32)
        self.assertEqual(self.analysis.mcnemar(0, 0), 1.0)
        self.assertEqual(self.analysis.lopsided_enough(7), 0)
        self.assertEqual(self.analysis.lopsided_enough(10), 1)
        self.assertIsNone(self.analysis.lopsided_enough(5))
        self.assertLess(self.analysis.mcnemar(8, 1), 0.05)  # a gap can count with a loss on the other side
        self.assertGreater(self.analysis.mcnemar(7, 1), 0.05)

    def test_paired_difference_interval_is_newcombes_method_10_with_his_correction(self):
        # both solved, only the first, only the second, neither; then the difference and its 95% interval in points
        for cells, expected in {(54, 5, 2, 5): (4.5, -4.3, 13.8), (51, 3, 5, 7): (-3.0, -12.5, 6.2),
                                (52, 2, 4, 8): (-3.0, -11.6, 5.3), (55, 2, 1, 8): (1.5, -5.3, 8.6)}.items():
            got = tuple(round(100 * x, 1) for x in self.analysis.paired_interval(*cells))
            self.assertEqual(got, expected, cells)
        difference, low, high = self.analysis.paired_interval(60, 0, 0, 6)
        self.assertEqual(difference, 0.0)
        self.assertAlmostEqual(low, -high)


if __name__ == "__main__":
    unittest.main()
