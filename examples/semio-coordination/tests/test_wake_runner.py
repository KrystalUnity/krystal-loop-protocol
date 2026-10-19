"""Offline one-job dispatch tests; no processes, sockets, or model calls."""
import copy
from datetime import datetime, timezone
import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[1] / "wake_runner.py"
SPEC = importlib.util.spec_from_file_location("wake_runner", PATH)
wake = importlib.util.module_from_spec(SPEC)
if PATH.exists():
    SPEC.loader.exec_module(wake)

TRIGGER = {"protocol": "klp-core/v0.3", "mission_id": "mission", "mission_revision": 1,
           "mission_hash": "a" * 64, "task_id": "task", "contract_id": "contract",
           "contract_revision": 1, "artifact_revision": "candidate", "unit_id": "review",
           "from": "coordinator", "to": "worker", "message_id": "notify-1", "kind": "handover"}


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


class Clock:
    def __init__(self):
        self.now = 1800000000.0
        self.elapsed = 0.0

    def wall(self):
        return self.now + self.elapsed

    def mono(self):
        return self.elapsed

    def sleep(self, seconds):
        self.elapsed += seconds


class FakeAdapter:
    def __init__(self):
        self.cursor = "19-0"
        self.messages = []
        self.delivered = []
        self.error = None

    def poll(self, *, batch_size):
        if self.error:
            raise self.error
        return copy.deepcopy(self.messages[:batch_size])

    def mark_delivered(self, message_id):
        self.delivered.append(message_id)


class WakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "job.sqlite")
        self.clock = Clock()
        self.adapter = FakeAdapter()
        self.executions = []
        self.waits = []

    def execute(self):
        self.executions.append("fixed-reviewed-job")

    def wait(self, cursor, seconds):
        self.waits.append((cursor, seconds))
        self.clock.sleep(seconds)

    def event(self, **changes):
        envelope = dict(TRIGGER, timestamp=stamp(self.clock.wall()), summary="Not a command")
        envelope.update(changes)
        return envelope

    def open(self, **changes):
        opts = dict(trigger=TRIGGER, job_id="job-1", job_hash="b" * 64,
                    expires_at=stamp(self.clock.now + 100), execute=self.execute,
                    runner_timeout_seconds=10, wait_for_event=self.wait,
                    monotonic=self.clock.mono, wall_time=self.clock.wall, sleep=self.clock.sleep)
        opts.update(changes)
        runner = wake.WakeRunner(self.adapter, self.path, **opts)
        self.addCleanup(runner.close)
        return runner

    def test_api_exists(self):
        self.assertTrue(hasattr(wake, "WakeRunner"), "runner API not implemented")

    def test_default_off_and_idle_never_launch(self):
        runner = self.open()
        self.adapter.messages = [self.event()]
        self.assertEqual(runner.run(timeout=1), "disabled")
        self.assertEqual(runner.counters["scan_calls"], 0)
        self.adapter.messages = []
        self.assertEqual(runner.run(armed=True, timeout=1), "idle")
        self.assertEqual(self.executions, [])
        self.assertEqual(runner.state, "ready")

    def test_claim_is_durable_before_no_argument_callback(self):
        states = []
        def execute():
            with sqlite3.connect(self.path) as db:
                states.append(db.execute("SELECT state FROM job").fetchone()[0])
            self.execute()
        runner = self.open(execute=execute)
        self.adapter.messages = [self.event()]
        self.assertEqual(runner.run(armed=True, timeout=0), "completed")
        self.assertEqual(states, ["claimed"])
        self.assertEqual(self.executions, ["fixed-reviewed-job"])
        self.assertEqual(self.adapter.delivered, ["notify-1"])
        with self.assertRaises(wake.AlreadyAttemptedError):
            runner.run(armed=True, timeout=1)
        runner.close()
        self.adapter.messages = [self.event(message_id="fresh-message")]
        with self.assertRaises(wake.AlreadyAttemptedError):
            self.open().run(armed=True, timeout=1)
        self.assertEqual(len(self.executions), 1)

    def test_failed_callback_never_retried_after_reopen(self):
        def fail():
            self.execute()
            raise RuntimeError("launcher failed")
        runner = self.open(execute=fail)
        self.adapter.messages = [self.event()]
        with self.assertRaisesRegex(RuntimeError, "launcher failed"):
            runner.run(armed=True, timeout=1)
        self.assertEqual(runner.state, "failed")
        runner.close()
        with self.assertRaises(wake.AlreadyAttemptedError):
            self.open().run(armed=True, timeout=1)
        self.assertEqual(len(self.executions), 1)

    def test_crash_leaves_uncertain_claim_and_no_retry(self):
        def crash():
            self.execute()
            raise KeyboardInterrupt()
        runner = self.open(execute=crash)
        self.adapter.messages = [self.event()]
        with self.assertRaises(KeyboardInterrupt):
            runner.run(armed=True, timeout=1)
        self.assertEqual(runner.state, "claimed")
        runner.close()
        with self.assertRaises(wake.AlreadyAttemptedError):
            self.open().run(armed=True, timeout=1)
        self.assertEqual(len(self.executions), 1)

    def test_all_trigger_fields_type_checked_and_no_unknown_notification(self):
        runner = self.open()
        for key, value in TRIGGER.items():
            bad = value + 1 if type(value) is int else value + "-wrong"
            self.adapter.messages = [self.event(**{key: bad})]
            with self.subTest(key=key), self.assertRaises(wake.TriggerError):
                runner.run(armed=True, timeout=0)
        self.adapter.messages = [self.event(mission_revision=True)]
        with self.assertRaises(wake.TriggerError):
            runner.run(armed=True, timeout=0)
        self.assertEqual(self.executions, [])

    def test_entire_returned_batch_validated_before_claim(self):
        runner = self.open()
        self.adapter.messages = [self.event(), self.event(message_id="unknown")]
        with self.assertRaises(wake.TriggerError):
            runner.run(armed=True, timeout=0)
        self.assertEqual(runner.state, "ready")

    def test_replayed_pending_timestamp_and_expiry_revalidated(self):
        runner = self.open(max_age_seconds=5)
        self.adapter.messages = [self.event(timestamp=stamp(self.clock.wall()-6))]
        with self.assertRaises(wake.TriggerError):
            runner.run(armed=True, timeout=0)
        self.adapter.messages = [self.event(timestamp=stamp(self.clock.wall()+301))]
        with self.assertRaises(wake.TriggerError):
            runner.run(armed=True, timeout=0)
        self.clock.sleep(100)
        self.adapter.messages = [self.event()]
        with self.assertRaises(wake.ExpiredError):
            runner.run(armed=True, timeout=0)
        self.assertEqual(self.executions, [])

    def test_configuration_is_frozen_and_pinned_on_reopen(self):
        trigger = dict(TRIGGER)
        runner = self.open(trigger=trigger)
        trigger["unit_id"] = "mutated"
        self.adapter.messages = [self.event(unit_id="mutated")]
        with self.assertRaises(wake.TriggerError):
            runner.run(armed=True, timeout=0)
        runner.close()
        for changes in (dict(trigger=trigger), dict(job_hash="c"*64), dict(job_id="other"),
                        dict(expires_at=stamp(self.clock.now+101)), dict(runner_timeout_seconds=11)):
            with self.subTest(changes=changes), self.assertRaises(wake.ConfigurationError):
                self.open(**changes)

    def test_adapter_failures_propagate_without_launch(self):
        runner = self.open()
        for failure in (ValueError("invalid"), RuntimeError("trimmed cursor")):
            self.adapter.error = failure
            with self.assertRaises(type(failure)) as caught:
                runner.run(armed=True, timeout=0)
            self.assertIs(caught.exception, failure)
        self.assertEqual(self.executions, [])

    def test_callback_timeout_propagates_and_is_not_retried(self):
        def timeout():
            raise TimeoutError("host killed process group")
        runner = self.open(execute=timeout)
        self.adapter.messages = [self.event()]
        with self.assertRaises(TimeoutError):
            runner.run(armed=True, timeout=1)
        self.assertEqual(runner.state, "failed")
        with self.assertRaises(wake.AlreadyAttemptedError):
            runner.run(armed=True, timeout=1)

    def test_overlong_callback_is_failed_even_if_it_returns(self):
        runner = self.open(execute=lambda: self.clock.sleep(11))
        self.adapter.messages = [self.event()]
        with self.assertRaises(TimeoutError):
            runner.run(armed=True, timeout=1)
        self.assertEqual(runner.state, "failed")

    def test_event_wait_uses_saved_cursor_and_rescans_not_wait_payload(self):
        def signal(cursor, seconds):
            self.wait(cursor, min(seconds, 0.2))
            self.adapter.messages = [self.event()]
            return {"command": "ignored"}
        runner = self.open(wait_for_event=signal)
        self.assertEqual(runner.run(armed=True, timeout=1), "completed")
        self.assertEqual(self.waits, [("19-0", 0.2)])
        self.assertEqual(runner.counters, dict(scan_calls=2, event_wait_calls=1,
                                             poll_wait_calls=0, execute_calls=1))

    def test_poll_and_event_modes_use_same_trigger_and_callback(self):
        runner = self.open()
        self.assertEqual(runner.run(armed=True, timeout=0.3, mode="poll"), "idle")
        self.assertEqual(self.waits, [])
        self.assertGreaterEqual(runner.counters["poll_wait_calls"], 3)
        self.adapter.messages = [self.event()]
        self.assertEqual(runner.run(armed=True, timeout=0, mode="poll"), "completed")
        self.assertEqual(self.executions, ["fixed-reviewed-job"])

    def test_invalid_limits_and_missing_binding_rejected(self):
        for field in TRIGGER:
            trigger = dict(TRIGGER)
            del trigger[field]
            with self.subTest(field=field), self.assertRaises(wake.ConfigurationError):
                self.open(trigger=trigger)
        runner = self.open()
        for timeout in (-1, float("nan"), float("inf")):
            with self.assertRaises(wake.ConfigurationError):
                runner.run(armed=True, timeout=timeout)
        with self.assertRaises(wake.ConfigurationError):
            runner.run(armed="yes", timeout=0)


if __name__ == "__main__":
    unittest.main()
