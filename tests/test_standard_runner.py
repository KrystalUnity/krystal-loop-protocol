"""Offline tests for the Standard runner: scripted models, real sandbox, no network, no spend."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal as D
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from klp.llm import Ledger, Model, ProviderError, price, rates_at, read_usage, reply_from  # noqa: E402
from klp.review import (critic_system, disposition, parse_verdict, probe_command, project_test_rules,  # noqa: E402
                        run_acceptance, under_project_rules)
from klp.sandbox import Sandbox  # noqa: E402
from klp.standard import Limits, run_standard  # noqa: E402

WORKER = Model("cheap-worker", "http://worker.invalid/v1", "KLP_TEST_KEY", "alpha")
CRITIC = Model("strong-critic", "http://critic.invalid/v1", "KLP_TEST_KEY", "beta")
PRICES = {"cheap-worker": {"input": 1, "cached": 0.1, "write": 1, "output": 2},
          "strong-critic": {"input": 10, "cached": 1, "write": 10, "output": 20}}
USAGE = {"prompt_tokens": 1000, "completion_tokens": 100, "prompt_tokens_details": {"cached_tokens": 400}}


def bash(command: str) -> dict:
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": "c1", "type": "function", "function": {"name": "bash", "arguments": json.dumps({"command": command})}}]}


def say(text: str) -> dict:
    return {"role": "assistant", "content": text}


def verdict(*findings: dict, profile: str = "eligible", **more) -> dict:
    blocking = any(f["blocking"] for f in findings)
    return say(json.dumps({"verdict": "FAIL" if blocking else "PASS", "profile_assessment": profile,
                           "findings": list(findings), **more}))


def finding(claim: str, probe_body: str | None) -> dict:
    probe = None if probe_body is None else {"filename": "probe.py", "content": probe_body,
                                             "command": "python3 /workspace/probes/probe.py"}
    return {"id": "F1", "claim": claim, "blocking": True, "evidence": "diff", "probe": probe}


class Script:
    """Scripted provider: worker and critic replies are consumed in order."""

    def __init__(self, worker: list, critic: list):
        self.worker, self.critic, self.requests = list(worker), list(critic), []

    def __call__(self, url, key, body, timeout):
        self.requests.append(body)
        queue = self.critic if "response_format" in body else self.worker
        if not queue:
            return 500, "script exhausted"
        return 200, json.dumps({"model": body["model"], "usage": USAGE,
                                "choices": [{"finish_reason": "stop", "message": queue.pop(0)}]})


def sandbox_works() -> bool:
    """bubblewrap is installed and this host lets it create namespaces."""
    if not (shutil.which("bwrap") and shutil.which("git")):
        return False
    probe = Path(tempfile.mkdtemp(prefix="klp-probe-"))
    try:
        return Sandbox(probe).run("true", cwd="/workspace")["returncode"] == 0
    except Exception:
        return False
    finally:
        shutil.rmtree(probe, ignore_errors=True)


@unittest.skipUnless(sandbox_works(), "needs bubblewrap with user namespaces, and git")
class StandardLoop(unittest.TestCase):
    def setUp(self):
        os.environ["KLP_TEST_KEY"] = "not-a-real-key"
        self.tmp = Path(tempfile.mkdtemp(prefix="klp-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        repo = self.tmp / "ws" / "repo"
        repo.mkdir(parents=True)
        (repo / "calc.py").write_text("def double(x):\n    return x\n")
        (repo / "check.py").write_text("import calc\nassert callable(calc.double)\n")
        for args in (["init", "-q"], ["add", "-A"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "base"]):
            subprocess.run(["git", "-C", str(repo), *args], check=True)

    def run_loop(self, worker: list, critic: list, *, critic_model=CRITIC, cap=5.0, checks=("python3 check.py",),
                 acceptance=False):
        script = Script(worker, critic)
        ledger = Ledger(self.tmp / "ledger.jsonl", cap, prices=PRICES, transport=script)
        receipt = run_standard(ledger=ledger, worker=WORKER, critic=critic_model, sandbox=Sandbox(self.tmp / "ws"),
                               task="Make double(x) return twice x.", checks=list(checks), scope="t1",
                               limits=Limits(max_steps=5, repair_steps=5), out_dir=self.tmp / "out", acceptance=acceptance)
        return receipt, script, ledger

    def source(self) -> str:
        return (self.tmp / "ws/repo/calc.py").read_text()

    def test_confirmed_finding_is_repaired_and_rereviewed(self):
        wrong = bash("printf 'def double(x):\\n    return x + 2\\n' > calc.py")
        right = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        probe = "import sys; sys.path.insert(0, '/workspace/repo'); import calc; assert calc.double(5) == 10"
        receipt, script, _ = self.run_loop([wrong, say("done"), right, say("fixed")],
                                           [verdict(finding("double(5) is 7", probe)), verdict()])
        self.assertEqual(receipt["completion"]["state"], "completed")
        self.assertEqual([r["verdict"] for r in receipt["reviews"]], ["FAIL", "PASS"])
        self.assertEqual(receipt["reviews"][0]["findings"][0]["disposition"], "confirmed")
        self.assertTrue(receipt["repairs"][0]["probes"][0]["closed"])
        self.assertIn("x * 2", self.source())
        self.assertEqual(receipt["completion"]["final_revision"], receipt["candidates"][-1]["revision"])
        # The review is bound to the exact commit it judged, and the repair was reviewed too.
        self.assertEqual([r["reviewed_revision"] for r in receipt["reviews"]], [c["revision"] for c in receipt["candidates"]])
        self.assertTrue((self.tmp / "out/receipt.md").read_text().startswith("# KLP Standard receipt"))

    def test_open_finding_stays_open_until_its_probe_passes(self):
        wrong = bash("printf 'def double(x):\\n    return x + 2\\n' > calc.py")
        still_wrong = bash("printf 'def double(x):\\n    return x + 3\\n' > calc.py")
        probe = "import sys; sys.path.insert(0, '/workspace/repo'); import calc; assert calc.double(5) == 10"
        # The critic passes both repairs, but its own probe still fails, so the finding is carried, not dropped.
        still_failing = say(json.dumps({"verdict": "FAIL", "profile_assessment": "eligible", "findings": []}))
        receipt, _, _ = self.run_loop([wrong, say("done"), still_wrong, say("fixed"), still_wrong, say("fixed again")],
                                      [verdict(finding("double(5) is 7", probe)), verdict(), still_failing])
        self.assertEqual(receipt["completion"]["state"], "budget_exhausted")
        self.assertEqual([r["verdict"] for r in receipt["reviews"]], ["FAIL", "PASS", "FAIL"])
        carried = receipt["reviews"][-1]["findings"][0]
        self.assertEqual((carried["id"], carried["disposition"], carried["carried"]), ("F1", "confirmed", True))
        self.assertEqual([f["id"] for f in receipt["completion"]["unresolved_findings"]], ["F1"])
        self.assertIn("still open from an earlier review", (self.tmp / "out/receipt.md").read_text())

    def test_critic_can_withdraw_an_open_finding(self):
        right = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        probe = "import sys; sys.path.insert(0, '/workspace/repo'); import calc; assert calc.double(5) == 11"
        receipt, script, _ = self.run_loop([right, say("done"), bash("true"), say("the probe asks for 11; twice 5 is 10")],
                                           [verdict(finding("double(5) should be 11", probe)), verdict(withdrawn=["F1"])])
        self.assertEqual(receipt["completion"]["state"], "completed")
        self.assertEqual(receipt["reviews"][1]["withdrawn"], ["F1"])
        self.assertEqual(receipt["reviews"][1]["findings"], [])
        reviews = [r for r in script.requests if "response_format" in r]
        self.assertNotIn('"withdrawn"', reviews[0]["messages"][0]["content"])
        self.assertIn('"withdrawn"', reviews[1]["messages"][0]["content"])

    def test_acceptance_file_is_executed_and_its_failure_is_repaired(self):
        wrong = bash("printf 'def double(x):\\n    return x + 2\\n' > calc.py")
        right = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        accept = {"filename": "accept.py", "command": "python3 /workspace/probes/accept.py",
                  "content": "import sys; sys.path.insert(0, '/workspace/repo'); import calc\n"
                             "# 'return twice x'\nassert calc.double(5) == 10\n"}
        receipt, script, _ = self.run_loop([wrong, say("done"), right, say("fixed")],
                                           [verdict(acceptance=accept), verdict()], acceptance=True)
        first = receipt["reviews"][0]
        self.assertEqual(first["verdict"], "PASS")  # the critic saw nothing; its executed acceptance file did
        self.assertEqual(first["acceptance"]["result"], "failed")
        self.assertEqual([(f["id"], f["source"], f["disposition"]) for f in first["findings"]], [("A1", "acceptance", "confirmed")])
        self.assertTrue(receipt["repairs"][0]["probes"][0]["closed"])
        self.assertEqual(receipt["completion"]["state"], "completed")
        reviews = [r for r in script.requests if "response_format" in r]
        self.assertIn('"acceptance"', reviews[0]["messages"][0]["content"])
        self.assertNotIn('"acceptance"', reviews[1]["messages"][0]["content"])  # asked for once, on the first review

    def test_command_critic_reviews_without_a_metered_call(self):
        right = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        cli_critic = Model("seat-critic", "", "", "gamma", api="command", command=("some-agent", "--print", "{prompt}"),
                           reply="json:response")
        script = Script([right, say("done")], [])
        ledger = Ledger(self.tmp / "ledger.jsonl", 5.0, prices=PRICES, transport=script)
        seen = []

        def runner(model, prompt, timeout):
            seen.append(prompt)
            return json.dumps({"response": "```json\n" + json.dumps({"verdict": "PASS", "findings": []}) + "\n```"})

        ledger.command_runner = runner
        receipt = run_standard(ledger=ledger, worker=WORKER, critic=cli_critic, sandbox=Sandbox(self.tmp / "ws"),
                               task="Make double(x) return twice x.", checks=["python3 check.py"], scope="t1",
                               limits=Limits(max_steps=5, repair_steps=5), out_dir=self.tmp / "out")
        self.assertEqual(receipt["completion"]["state"], "completed")
        self.assertIn("# TASK STATEMENT", seen[0])
        critic_row = [r for r in ledger.rows if r["role"] == "critic"][0]
        self.assertEqual((critic_row["metered"], critic_row["usd"]), (False, "0"))
        self.assertEqual(ledger.summary(scope="t1")["critic"]["unmetered_calls"], 1)
        self.assertIn("subscription route, not metered", (self.tmp / "out/receipt.md").read_text())

    def test_refuted_finding_starts_no_repair(self):
        right = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        probe = "import sys; sys.path.insert(0, '/workspace/repo'); import calc; assert calc.double(5) == 10"
        receipt, script, _ = self.run_loop([right, say("done")], [verdict(finding("I think it is wrong", probe))])
        self.assertEqual(receipt["completion"]["state"], "completed")
        self.assertEqual(receipt["reviews"][0]["findings"][0]["disposition"], "refuted")
        self.assertEqual(receipt["repairs"], [])
        self.assertEqual(len(script.requests), 3)  # two worker turns, one review, nothing else

    def test_finding_without_probe_is_not_acted_on(self):
        receipt, _, _ = self.run_loop([bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py"), say("done")],
                                      [verdict(finding("opinion only", None))])
        self.assertEqual(receipt["repairs"], [])
        self.assertEqual(receipt["completion"]["unresolved_findings"][0]["disposition"], "unverified")

    def test_failed_declared_check_triggers_repair(self):
        broken = bash("printf 'def double(x)\\n' > calc.py")
        fixed = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        receipt, _, _ = self.run_loop([broken, say("done"), fixed, say("fixed")], [verdict(), verdict()])
        self.assertFalse(receipt["candidates"][0]["checks_passed"])
        self.assertTrue(receipt["completion"]["checks_passed"])
        self.assertEqual(receipt["completion"]["state"], "completed")

    def test_repair_that_breaks_checks_is_discarded(self):
        good = bash("printf 'def double(x):\\n    return x + x\\n' > calc.py")
        breaks = bash("printf 'def double(x)\\n' > calc.py")
        probe = "import sys; sys.exit(1)"
        receipt, _, _ = self.run_loop([good, say("done"), breaks, say("fixed")], [verdict(finding("claim", probe))])
        self.assertFalse(receipt["repairs"][0]["kept"])
        self.assertEqual(receipt["completion"]["final_revision"], receipt["candidates"][0]["revision"])
        self.assertIn("x + x", self.source())
        self.assertEqual(receipt["completion"]["state"], "budget_exhausted")

    def test_unreviewed_run_has_no_critic_calls(self):
        receipt, script, _ = self.run_loop([bash("true"), say("done")], [], critic_model=None)
        self.assertEqual(receipt["completion"]["state"], "unreviewed")
        self.assertEqual(len(script.requests), 2)

    def test_same_family_critic_is_refused(self):
        with self.assertRaises(ValueError):
            self.run_loop([], [], critic_model=Model("other", "http://x.invalid", "KLP_TEST_KEY", "alpha"))

    def test_cost_limit_stops_the_run(self):
        receipt, script, ledger = self.run_loop([bash("true")] * 5, [], cap=0.0015)
        self.assertEqual(receipt["completion"]["state"], "budget_exhausted")
        self.assertLessEqual(len(script.requests), 3)
        self.assertEqual(str(ledger.spent()), receipt["completion"]["measured_effort"]["usd"])

    def test_critical_trigger_stops_without_repair(self):
        probe = "import sys; sys.exit(1)"
        receipt, _, _ = self.run_loop([bash("true"), say("done")],
                                      [verdict(finding("touches billing", probe), profile="critical_trigger")])
        self.assertEqual(receipt["completion"]["state"], "critical_trigger")
        self.assertEqual(receipt["repairs"], [])

    def test_sandbox_hides_host_secrets_and_network(self):
        os.environ["KLP_SECRET_FOR_TEST"] = "hunter2"
        self.addCleanup(os.environ.pop, "KLP_SECRET_FOR_TEST", None)
        box = Sandbox(self.tmp / "ws")
        seen = box.run("env; ls /root 2>&1; ls /home 2>&1; cat /proc/net/dev | wc -l")["output"]
        self.assertNotIn("hunter2", seen)
        self.assertNotIn("KLP_TEST_KEY", seen)
        self.assertIn("No such file", seen)
        self.assertTrue(box.run("sleep 5", timeout=1)["timed_out"])


    def test_planted_symlinks_cannot_redirect_host_reads_or_writes(self):
        victim = self.tmp / "host-secret.txt"
        victim.write_text("host secret")
        # The worker replaces the probe folder with a link to a host directory before review.
        plant = bash(f"printf 'def double(x):\\n    return x * 2\\n' > calc.py; ln -s {self.tmp} /workspace/probes")
        probe = {"id": "F1", "claim": "c", "blocking": True, "evidence": "e",
                 "probe": {"filename": "host-secret.txt", "content": "overwritten", "command": "false"}}
        receipt, script, _ = self.run_loop([plant, say("done"), say("no change")], [verdict(probe), verdict()])
        self.assertEqual(victim.read_text(), "host secret")
        packet = script.requests[2]["messages"][1]["content"]
        self.assertNotIn("host secret", packet)


    def test_review_sees_the_real_change_whatever_the_worker_does_to_git(self):
        # The worker hides its edit behind a binary attribute, an external diff driver and a text
        # converter, then deletes the repository's own history. The critic must still see the edit.
        hide = bash("printf 'def double(x):\\n    return x * 2  # HIDDEN-EDIT\\n' > calc.py; "
                    "printf '*.py -diff diff=fake\\n' > .gitattributes; "
                    "git config diff.external /bin/true; git config diff.fake.textconv /bin/true; "
                    "git config diff.fake.command /bin/true; rm -rf .git")
        receipt, script, _ = self.run_loop([hide, say("done")], [verdict()])
        packet = script.requests[2]["messages"][1]["content"]
        self.assertIn("HIDDEN-EDIT", packet)
        self.assertIn(".gitattributes", packet)
        self.assertEqual(receipt["completion"]["state"], "completed")

    def test_review_resumes_from_a_recorded_unreviewed_run(self):
        wrong = bash("printf 'def double(x):\\n    return x + 2\\n' > calc.py")
        right = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py")
        built, _, _ = self.run_loop([wrong, say("done")], [], critic_model=None)
        transcript = json.loads((self.tmp / "out/worker-transcript.json").read_text())
        # Another arm reviews that exact candidate from copies of the workspace and snapshot store.
        shutil.copytree(self.tmp / "ws", self.tmp / "ws2", symlinks=True)
        shutil.copytree(self.tmp / "out/snapshots", self.tmp / "out2/snapshots", symlinks=True)
        probe = "import sys; sys.path.insert(0, '/workspace/repo'); import calc; assert calc.double(5) == 10"
        script = Script([right, say("fixed")], [verdict(finding("double(5) is 7", probe)), verdict()])
        ledger = Ledger(self.tmp / "ledger2.jsonl", 5.0, prices=PRICES, transport=script)
        receipt = run_standard(ledger=ledger, worker=WORKER, critic=CRITIC, sandbox=Sandbox(self.tmp / "ws2"),
                               task="Make double(x) return twice x.", checks=["python3 check.py"], scope="t2",
                               limits=Limits(max_steps=5, repair_steps=5), out_dir=self.tmp / "out2",
                               resume=dict(receipt=built, messages=transcript))
        self.assertEqual(receipt["completion"]["state"], "completed")
        self.assertEqual(receipt["candidates"][0]["revision"], built["candidates"][0]["revision"])
        self.assertEqual(receipt["reviews"][0]["reviewed_revision"], built["candidates"][0]["revision"])
        self.assertEqual(sorted(ledger.summary(scope="t2")), ["critic", "repair"])  # the build was not repeated
        self.assertIn("x * 2", (self.tmp / "ws2/repo/calc.py").read_text())
        self.assertIn("x + 2", (self.tmp / "ws/repo/calc.py").read_text())  # the recorded run is untouched

    def test_runner_git_ignores_a_planted_git_on_the_worker_path(self):
        from klp.snapshot import Snapshots
        tools = self.tmp / "ws" / "repo" / "tools"
        tools.mkdir()
        (tools / "git").write_text("#!/bin/sh\necho PLANTED > /workspace/planted\nexit 0\n")
        (tools / "git").chmod(0o755)
        box = Sandbox(self.tmp / "ws", path_prefix="/workspace/repo/tools")
        snapshots = Snapshots(box, self.tmp / "store")
        first = snapshots.take("one")
        self.assertRegex(first, r"^[0-9a-f]{40}$")
        self.assertFalse((self.tmp / "ws" / "planted").exists())

    def test_delivered_patch_is_the_reviewed_change(self):
        from klp.snapshot import Snapshots
        edit = bash("printf 'def double(x):\\n    return x * 2\\n' > calc.py; printf 'note\\n' > NEW.txt")
        receipt, _, _ = self.run_loop([edit, say("done")], [verdict()])
        patch = Snapshots(Sandbox(self.tmp / "ws"), self.tmp / "out" / "snapshots").patch(
            receipt["base_revision"], receipt["completion"]["final_revision"])
        clone = self.tmp / "clone"
        subprocess.run(["git", "clone", "-q", str(self.tmp / "ws/repo"), str(clone)], check=True)
        subprocess.run(["git", "-C", str(clone), "apply", "--binary"], input=patch, check=True)
        self.assertIn("x * 2", (clone / "calc.py").read_text())
        self.assertEqual((clone / "NEW.txt").read_text(), "note\n")


class Config(unittest.TestCase):
    def test_repository_config_cannot_set_routes_limits_or_sandbox(self):
        from klp import cli
        root = Path(tempfile.mkdtemp(prefix="klp-cfg-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        (root / "klp.json").write_text(json.dumps({
            "checks": ["make test"], "critical_triggers": ["billing code"],
            "worker": {"base_url": "https://attacker.invalid", "api_key_env": "OPENAI_API_KEY"},
            "sandbox": {"read_only_paths": ["/root/.ssh"], "network": True}, "limits": {"cost_usd": 999}}))
        user = root / "user.json"
        user.write_text(json.dumps({"limits": {"cost_usd": 0.5}}))
        config = cli.load_config(root, str(user))
        self.assertEqual(config["checks"], ["make test"])
        self.assertEqual(config["critical_triggers"], ["billing code"])
        self.assertEqual(config["worker"]["base_url"], cli.USER_CONFIG["worker"]["base_url"])
        self.assertEqual(config["sandbox"], cli.USER_CONFIG["sandbox"])
        self.assertEqual(config["limits"]["cost_usd"], 0.5)


class Parsing(unittest.TestCase):
    def test_verdict_is_strict(self):
        ok = parse_verdict(json.dumps({"verdict": "PASS", "profile_assessment": "eligible", "findings": []}))
        self.assertEqual(ok["verdict"], "PASS")
        twice = json.dumps({"verdict": "PASS", "findings": []}) * 2  # the same object emitted twice is one answer
        self.assertEqual(parse_verdict(twice)["verdict"], "PASS")
        with self.assertRaises(ValueError):
            parse_verdict(json.dumps({"verdict": "PASS", "findings": []}) + json.dumps({"verdict": "FAIL", "findings": []}))
        for bad in ("looks fine {\"verdict\": \"PASS\", \"findings\": []}", "{}",
                    json.dumps({"verdict": "PASS", "findings": [{"claim": "x", "blocking": True}]}),
                    json.dumps({"verdict": "FAIL", "findings": []})):
            with self.assertRaises(ValueError):
                parse_verdict(bad)
        # On a re-review with an earlier finding still open, FAIL needs no new finding. PASS with a blocker never parses.
        self.assertEqual(parse_verdict(json.dumps({"verdict": "FAIL", "findings": []}), open_earlier=True)["verdict"], "FAIL")
        with self.assertRaises(ValueError):
            parse_verdict(json.dumps({"verdict": "PASS", "findings": [{"claim": "x", "blocking": True}]}), open_earlier=True)

    def test_probe_dispositions(self):
        run = lambda rc, timed_out=False: dict(returncode=rc, timed_out=timed_out)  # noqa: E731
        self.assertEqual(disposition(run(0), "python -m pytest p.py"), "refuted")
        self.assertEqual(disposition(run(1), "python -m pytest p.py"), "confirmed")
        self.assertEqual(disposition(run(2), "python -m pytest p.py"), "unverified")
        self.assertEqual(disposition(run(3), "go test ./..."), "confirmed")
        self.assertEqual(disposition(run(None, True), "go test ./..."), "unverified")

    def test_optional_reply_parts(self):
        accept = {"filename": "t.py", "content": "x", "command": "python t.py"}
        got = parse_verdict(json.dumps({"verdict": "PASS", "findings": [], "acceptance": accept, "withdrawn": ["A2", 3]}))
        self.assertEqual((got["acceptance"], got["withdrawn"]), (accept, ["A2", "3"]))
        plain = parse_verdict(json.dumps({"verdict": "PASS", "findings": [], "acceptance": {"filename": "t.py"}}))
        self.assertEqual((plain["acceptance"], plain["withdrawn"]), (None, []))
        self.assertIn("first review", critic_system(acceptance=True))
        self.assertNotIn("first review", critic_system())

    def test_pytest_probes_run_under_the_project_rules(self):
        rules = dict(file="pyproject.toml", settings="{}")
        self.assertEqual(under_project_rules("python -m pytest -q /workspace/probes/t.py", rules, "/workspace/repo"),
                         "python -m pytest -c /workspace/repo/pyproject.toml --rootdir /workspace/repo -q /workspace/probes/t.py")
        # However the critic spells its probe file, the command gets the path the runner wrote it to.
        for spelled in ("probes/test_f1.py", "test_f1.py", "tests/../workspace/probes/test_f1.py", "/workspace/probes/test_f1.py"):
            probe = {"filename": "test_f1.py", "content": "x", "command": f"python -m pytest -q {spelled}::test_a"}
            self.assertEqual(probe_command(probe, None, "/workspace/repo"),
                             ("/workspace/probes/test_f1.py", "python -m pytest -q /workspace/probes/test_f1.py::test_a"))
        for untouched in ("python3 /workspace/probes/t.py", "python -m pytest -c other.ini t.py", "go test ./..."):
            self.assertEqual(under_project_rules(untouched, rules, "/workspace/repo"), untouched)
        self.assertEqual(under_project_rules("pytest t.py", None, "/r"), "pytest t.py")

        class Files:
            def __init__(self, files):
                self.files = files

            def run(self, command, **_):
                name = command.split()[-1]
                return dict(returncode=0 if name in self.files else 1, output=self.files.get(name, ""), timed_out=False)

        toml = '[tool.pytest.ini_options]\nfilterwarnings = ["error"]\n'
        self.assertEqual(project_test_rules(Files({"pyproject.toml": toml}))["file"], "pyproject.toml")
        self.assertIn("error", project_test_rules(Files({"pyproject.toml": toml}))["settings"])
        self.assertEqual(project_test_rules(Files({"setup.cfg": "[tool:pytest]\naddopts = -ra\n", "pyproject.toml": "[project]\n"}))["file"],
                         "setup.cfg")
        self.assertIsNone(project_test_rules(Files({"pyproject.toml": "[project]\nname = 'x'\n"})))

    def test_each_failing_acceptance_test_is_one_finding(self):
        summary = ("F.F\n=== short test summary info ===\n"
                   "FAILED ::test_default - assert 1 == 2\n"
                   "FAILED ../probes/test_acceptance.py::test_rejects[US-11] - AssertionError\n2 failed, 1 passed\n")

        class Box:
            repo_dir = "/workspace/repo"
            commands: list = []

            def write_file(self, path, content):
                self.written = path

            def run(self, command, **_):
                self.commands.append(command)
                if "::" not in command:
                    return dict(returncode=1, timed_out=False, output=summary)
                # alone, the parametrised case passes: it only failed beside the others, so it is not evidence
                return dict(returncode=0 if "test_rejects" in command else 1, timed_out=False, output="assert 1 == 2")

        class Snaps:
            def restore(self, revision):
                pass

        box = Box()
        accept = {"filename": "test_acceptance.py", "content": "...", "command": "python -m pytest -q -x /workspace/probes/test_acceptance.py"}
        record, findings = run_acceptance(box, Snaps(), accept, "head")
        self.assertNotIn(" -x", box.commands[0])
        self.assertEqual(record["result"], "failed")
        self.assertEqual(record["failed_tests"], ["test_default", "test_rejects[US-11]"])
        self.assertEqual([f["id"] for f in findings], ["A1"])
        self.assertEqual(findings[0]["probe"]["command"], "python -m pytest -q /workspace/probes/test_acceptance.py::test_default")
        self.assertIn("'/workspace/probes/test_acceptance.py::test_rejects[US-11]'", box.commands[2])

    def test_command_replies(self):
        self.assertEqual(reply_from('{"response": "{\\"a\\": 1}\\n"}', "json:response"), '{"a": 1}')
        lines = '{"role":"meta","type":"v"}\n{"role":"assistant","content":"first"}\n{"role":"assistant","content":"{}"}\n'
        self.assertEqual(reply_from(lines, "ndjson:content"), "{}")
        self.assertEqual(reply_from("```json\n{}\n```\n", "text"), "{}")
        chatty = 'I could not open the repository, so this is from the packet {see above}.\n\n{"verdict": "PASS", "findings": []}'
        self.assertEqual(reply_from(chatty, "text"), '{"verdict": "PASS", "findings": []}')
        self.assertEqual(reply_from("Here it is:\n```json\n{\"a\": 1}\n```", "text"), '{"a": 1}')
        self.assertEqual(reply_from("no object here", "text"), "no object here")
        for broken in (("not json", "json:response"), ('{"other": 1}', "json:response"), ('{"role":"meta"}', "ndjson:content")):
            with self.assertRaises(ProviderError):
                reply_from(*broken)

    def test_off_peak_rates_and_reasoning_tokens(self):
        entry = {"input": 0.3, "cached": 0.006, "write": 0.3, "output": 1.2,
                 "off_peak": {"input": 0.15, "cached": 0.003, "write": 0.15, "output": 0.6},
                 "peak_utc": {"days": [0, 1, 2, 3, 4], "hours": [[1, 4], [6, 10]]}}
        import calendar
        at = lambda text: calendar.timegm(__import__("time").strptime(text, "%Y-%m-%d %H:%M"))  # noqa: E731
        self.assertEqual(rates_at(entry, at("2026-11-10 07:30")), (entry, "standard"))          # Tuesday, peak
        self.assertEqual(rates_at(entry, at("2026-11-10 10:00")), (entry["off_peak"], "off_peak"))
        self.assertEqual(rates_at(entry, at("2026-11-14 07:30"))[1], "off_peak")                  # Saturday
        self.assertEqual(rates_at({"input": 1, "output": 2}, at("2026-11-10 12:00"))[1], "standard")
        self.assertEqual(price(dict(input=1000, cached=0, write=0, output=1000), entry), D("0.0015"))
        # A provider that reports reasoning outside the completion count still bills it as output.
        xai = {"prompt_tokens": 1299, "completion_tokens": 17, "total_tokens": 1527, "prompt_tokens_details": {"cached_tokens": 1152}}
        self.assertEqual(read_usage(xai), dict(input=1299, output=228, cached=1152, write=0))
        self.assertEqual(price(read_usage(xai), {"input": 2.0, "cached": 0.5, "write": 2.0, "output": 6.0}), D("0.002238"))

    def test_usage_and_price(self):
        usage = read_usage(USAGE)
        self.assertEqual(usage, dict(input=1000, output=100, cached=400, write=0))
        self.assertEqual(price(usage, PRICES["cheap-worker"]), D("0.00084"))
        self.assertIsNone(price(usage, None))
        with self.assertRaises(ProviderError):
            read_usage({"prompt_tokens": 10})


if __name__ == "__main__":
    unittest.main()
