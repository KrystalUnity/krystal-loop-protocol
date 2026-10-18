"""Offline adapter contract tests; no Redis or provider access."""
import copy
import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest
from datetime import datetime, timezone, timedelta

MODULE = Path(__file__).resolve().parents[1] / "semio_adapter.py"
spec = importlib.util.spec_from_file_location("semio_adapter", MODULE)
adapter = importlib.util.module_from_spec(spec)
if MODULE.exists():
    spec.loader.exec_module(adapter)

IDENTITY = dict(protocol="klp-core/v0.3", mission_id="mission", mission_revision=1,
                mission_hash="sha256:" + "a" * 64, task_id="task",
                contract_id="contract", contract_revision=1, artifact_revision="base")


def message(**changes):
    value = dict(IDENTITY, message_id="msg-1", unit_id="unit", kind="status",
                 correlation_id="flow", in_reply_to=None, affected_capabilities=[],
                 capability_report_ref=None, evidence_refs=[], summary="Factual status",
                 timestamp=datetime.now(timezone.utc).isoformat())
    value.update({"from": "worker", "to": "coordinator"})
    value.update(changes)
    return value


class FakeTransport:
    def __init__(self):
        self.entries = []
        self.scans = 0
        self.lookups = []
        self.serial = 0

    def publish(self, *, sender, to, kind, payload_dict, correlation_id=None,
                in_reply_to=None, nexus_ref=None):
        self.serial += 1
        entry = dict(id=f"{self.serial}-0", v="1", kind=kind,
                     payload=copy.deepcopy(payload_dict), correlation_id=correlation_id,
                     in_reply_to=in_reply_to or "", nexus_ref=nexus_ref or "")
        entry.update({"from": sender, "to": to})
        self.entries.append(entry)
        return entry["id"]

    def add(self, envelope):
        mapping = {"handover": "propose", "finding": "alert", "stop": "alert"}
        return self.publish(sender=envelope["from"], to=envelope["to"],
                            kind=mapping.get(envelope["kind"], envelope["kind"]),
                            payload_dict=envelope, correlation_id=envelope["correlation_id"],
                            in_reply_to=envelope["in_reply_to"])

    def read_entry(self, entry_id):
        self.lookups.append(entry_id)
        return next((copy.deepcopy(e) for e in self.entries if e["id"] == entry_id), None)

    def read_since(self, last_id="0-0", count=100):
        self.scans += 1
        key = lambda x: tuple(map(int, x.split("-")))
        return copy.deepcopy([e for e in self.entries if key(e["id"]) > key(last_id)][:count])


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = str(Path(self.temp.name) / "inbox.sqlite")
        self.transport = FakeTransport()

    def open(self, **changes):
        options = dict(identity=IDENTITY, agent="coordinator", allowed_senders={"worker"},
                       allowed_recipients={"worker"})
        options.update(changes)
        instance = adapter.SemioAdapter(self.transport, self.path, **options)
        self.addCleanup(instance.close)
        return instance

    def test_api_available(self):
        self.assertTrue(hasattr(adapter, "SemioAdapter"), "adapter API not implemented")

    def test_publish_maps_all_kinds_and_preserves_extensions(self):
        receiver = self.open()
        for kind, mapped in dict(status="status", question="question", answer="answer",
                                 handover="propose", finding="alert", stop="alert").items():
            envelope = message(kind=kind, **{"from": "coordinator", "to": "worker"},
                               extension={"nested": [1, True, None]})
            self.assertEqual(receiver.publish(envelope), self.transport.entries[-1]["id"])
            self.assertEqual(self.transport.entries[-1]["kind"], mapped)
            self.assertEqual(self.transport.entries[-1]["payload"], envelope)

    def test_durable_pending_replay_explicit_delivery_and_dedup(self):
        receiver = self.open()
        envelope = message()
        entry_id = self.transport.add(envelope)
        self.assertEqual(receiver.poll(), [envelope])
        receiver.close()
        receiver = self.open()
        self.assertEqual(receiver.pending(), [envelope])
        self.assertEqual(receiver.poll(), [envelope])
        self.assertIn(entry_id, self.transport.lookups)
        self.transport.add(envelope)
        self.assertEqual(receiver.poll(), [envelope])
        receiver.mark_delivered(envelope["message_id"])
        receiver.mark_delivered(envelope["message_id"])
        self.transport.add(envelope)
        self.assertEqual(receiver.poll(), [])
        receiver.close()
        self.assertEqual(self.open().pending(), [])

    def test_conflicting_id_stops_without_advancing(self):
        receiver = self.open()
        envelope = message()
        first = self.transport.add(envelope)
        receiver.poll()
        self.transport.add(dict(envelope, summary="changed"))
        with self.assertRaises(adapter.ConflictError):
            receiver.poll()
        self.assertEqual(receiver.cursor, first)
        self.assertEqual(receiver.pending(), [envelope])

    def test_trimmed_cursor_stops_before_scan_even_with_pending(self):
        receiver = self.open()
        self.transport.add(message())
        receiver.poll()
        receiver.close()
        self.transport.entries.clear()
        receiver = self.open()
        scans = self.transport.scans
        with self.assertRaises(adapter.CursorTrimmedError):
            receiver.poll()
        self.assertEqual(self.transport.scans, scans)
        self.assertEqual(len(receiver.pending()), 1)

    def test_wrong_binding_and_stale_and_malformed_fail_closed(self):
        receiver = self.open()
        cases = [dict(mission_id="other"), dict(mission_revision=2),
                 dict(mission_hash="sha256:" + "b" * 64), dict(task_id="other"),
                 dict(contract_id="other"), dict(contract_revision=2),
                 dict(artifact_revision="other"), dict(protocol="klp-core/v0.2"),
                 dict(mission_revision=True), dict(kind="act"), dict(summary=3),
                 dict(evidence_refs="bad"), dict(timestamp="not a timestamp"),
                 dict(timestamp=(datetime.now(timezone.utc)-timedelta(days=2)).isoformat()),
                 dict(timestamp=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()),
                 dict(summary="x" * 20000), dict(extension=float("nan"))]
        for changes in cases:
            with self.subTest(changes=list(changes)):
                self.transport.entries.clear()
                self.transport.add(message(**changes))
                with self.assertRaises(adapter.ValidationError):
                    receiver.poll()
                self.assertEqual(receiver.cursor, "0-0")
                self.assertEqual(receiver.pending(), [])

    def test_missing_required_field_and_outer_mismatch(self):
        receiver = self.open()
        for field in ("unit_id", "message_id", "timestamp", "summary", "affected_capabilities"):
            self.transport.entries.clear()
            value = message()
            del value[field]
            self.transport.add(value)
            with self.assertRaises(adapter.ValidationError):
                receiver.poll()
        for field, value in (("kind", "act"), ("correlation_id", "wrong"),
                             ("in_reply_to", "wrong"), ("payload_error", "bad JSON")):
            self.transport.entries.clear()
            self.transport.add(message())
            self.transport.entries[-1][field] = value
            with self.assertRaises(adapter.ValidationError):
                receiver.poll()

    def test_unrelated_sender_and_recipient_are_skipped(self):
        receiver = self.open()
        self.transport.add(message(**{"from": "stranger"}))
        self.transport.add(message(**{"to": "other"}))
        self.transport.add(message(**{"to": "*"}))
        self.assertEqual(receiver.poll(), [])
        self.assertEqual(receiver.cursor, "3-0")

    def test_publish_cannot_spoof_sender_or_use_unlisted_recipient(self):
        receiver = self.open()
        for value in (message(), message(**{"from": "coordinator", "to": "*"})):
            with self.assertRaises(adapter.ValidationError):
                receiver.publish(value)
        self.assertEqual(self.transport.entries, [])

    def test_database_identity_cannot_be_rebound(self):
        self.open().close()
        for changes in (dict(identity=dict(IDENTITY, artifact_revision="new")),
                        dict(agent="other"), dict(allowed_senders={"stranger"})):
            with self.assertRaises(adapter.ValidationError):
                self.open(**changes)

    def test_receipt_and_cursor_roll_back_together_on_storage_failure(self):
        receiver = self.open()
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TRIGGER deny_cursor BEFORE UPDATE OF value ON metadata "
                       "WHEN NEW.key = 'cursor' BEGIN SELECT RAISE(ABORT, 'disk failure'); END")
        self.transport.add(message())
        with self.assertRaises(sqlite3.DatabaseError):
            receiver.poll()
        self.assertEqual(receiver.cursor, "0-0")
        self.assertEqual(receiver.pending(), [])

    def test_batch_and_wait_are_bounded(self):
        receiver = self.open()
        start = time.monotonic()
        self.assertEqual(receiver.wait(timeout=0.02, poll_interval=0.005), [])
        self.assertLess(time.monotonic() - start, 0.5)
        for value in (-1, float("inf"), float("nan")):
            with self.assertRaises(adapter.ValidationError):
                receiver.wait(timeout=value)
        for value in (0, -1, 1001, True):
            with self.assertRaises(adapter.ValidationError):
                receiver.poll(batch_size=value)
        self.transport.add(message())
        self.transport.add(message(message_id="msg-2"))
        self.assertEqual(len(receiver.wait(timeout=0, batch_size=1)), 1)
        self.assertEqual(receiver.cursor, "1-0")
        with self.assertRaises(KeyError):
            receiver.mark_delivered("unknown")


if __name__ == "__main__":
    unittest.main()
