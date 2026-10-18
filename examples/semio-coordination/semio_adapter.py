"""Optional stdlib KLP notifications over an injected Semio CoordStream.

No authentication, authorization, execution, subprocesses, or model calls.
Use one consumer per local SQLite file; retain it for deduplication. Receipts
mean delivery only, never artifact acceptance or exactly-once job execution.
The host must bound transport socket/connect timeouts: wait bounds its polling
loop but cannot preempt a synchronous transport call. No KU import is required.
"""
from datetime import datetime, timezone
import json
import math
import re
import sqlite3
import time

KIND_MAP = {"status": "status", "question": "question", "answer": "answer",
            "handover": "propose", "finding": "alert", "stop": "alert"}
IDENTITY_FIELDS = {"protocol", "mission_id", "mission_revision", "mission_hash",
                   "task_id", "contract_id", "contract_revision", "artifact_revision"}


class ValidationError(ValueError):
    """Invalid configuration or addressed message; cursor is not advanced."""


class ConflictError(ValidationError):
    """A previously received message_id has different content; reconcile records."""


class CursorTrimmedError(RuntimeError):
    """Saved cursor is absent; reconcile durable records before resuming."""


def _text(value, *, limit=256, token=False):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValidationError("missing, invalid, or oversized text field")
    if token and (any(c.isspace() for c in value) or any(ord(c) < 32 for c in value)):
        raise ValidationError("identifier contains whitespace or controls")
    return value


def _json(value):
    def check(node, depth=0):
        if depth > 32:
            raise ValidationError("JSON nesting exceeds 32 levels")
        if type(node) is dict:
            for key, child in node.items():
                if type(key) is not str:
                    raise ValidationError("JSON keys must be strings")
                check(child, depth + 1)
        elif type(node) is list:
            for child in node:
                check(child, depth + 1)
        elif node is not None and type(node) not in (str, int, float, bool):
            raise ValidationError("payload must contain JSON values only")
    try:
        check(value)
        return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":"))
    except (TypeError, ValueError, RecursionError) as exc:
        raise ValidationError("invalid JSON payload") from exc


def _batch(value):
    if type(value) is not int or not 1 <= value <= 1000:
        raise ValidationError("batch/limit must be an integer from 1 to 1000")
    return value


def _seconds(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValidationError("time limit must be finite")
    if value < 0 or (positive and value == 0):
        raise ValidationError("invalid time limit")
    return value


class SemioAdapter:
    """Bind a local inbox to one identity and explicitly allowed peers.

    identity requires IDENTITY_FIELDS (protocol must be klp-core/v0.3).
    Extra identity fields, e.g. contract_hash or unit_id, are also exact-bound.
    mission_hash is a lowercase SHA-256 hex digest, optionally prefixed sha256:.
    agent is the only inbound recipient and outbound sender. No wildcard peers.
    The database binds identity, peers, and validation limits across reopen.
    poll skips unrelated outer sender/recipient pairs; malformed addressed
    traffic stops without skipping that entry. Names are claims, not auth.
    """

    def __init__(self, transport, db_path, *, identity, agent, allowed_senders,
                 allowed_recipients, max_payload_bytes=16384, max_age_seconds=86400):
        if type(identity) is not dict or not IDENTITY_FIELDS <= identity.keys():
            raise ValidationError("identity lacks required bindings")
        self._identity = json.loads(_json(identity))
        if identity["protocol"] != "klp-core/v0.3":
            raise ValidationError("unsupported protocol")
        for key, value in identity.items():
            if key in ("mission_revision", "contract_revision"):
                if type(value) is not int or value < 1:
                    raise ValidationError("revision must be a positive integer")
            else:
                _text(value, token=True)
        if not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", identity["mission_hash"]):
            raise ValidationError("invalid mission hash")
        def name(value):
            value = _text(value, token=True)
            if value == "*" or ":" in value:
                raise ValidationError("explicit Semio agent name required")
            return value
        self._agent = name(agent)
        if isinstance(allowed_senders, str) or isinstance(allowed_recipients, str):
            raise ValidationError("allowlists must be collections of names")
        self._senders = frozenset(name(v) for v in allowed_senders)
        self._recipients = frozenset(name(v) for v in allowed_recipients)
        if type(max_payload_bytes) is not int or not 1 <= max_payload_bytes <= 1048576:
            raise ValidationError("payload limit must be 1..1048576 bytes")
        self._max_bytes = max_payload_bytes
        self._max_age = _seconds(max_age_seconds, positive=True)
        self.transport = transport
        config = _json(dict(identity=self._identity, agent=self._agent,
                            senders=sorted(self._senders), recipients=sorted(self._recipients),
                            max_payload_bytes=max_payload_bytes, max_age_seconds=max_age_seconds))
        self._db = sqlite3.connect(db_path, timeout=2)
        try:
            self._db.execute("PRAGMA synchronous=FULL")
            with self._db:
                self._db.execute("CREATE TABLE IF NOT EXISTS metadata "
                                 "(key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                self._db.execute("CREATE TABLE IF NOT EXISTS inbox "
                                 "(message_id TEXT PRIMARY KEY, envelope TEXT NOT NULL, "
                                 "entry_id TEXT NOT NULL, delivered INTEGER NOT NULL DEFAULT 0)")
                self._db.execute("INSERT OR IGNORE INTO metadata VALUES ('config', ?)", (config,))
                if self._db.execute("SELECT value FROM metadata WHERE key='config'").fetchone()[0] != config:
                    raise ValidationError("inbox configuration differs; do not rebind receipts")
                self._db.execute("INSERT OR IGNORE INTO metadata VALUES ('cursor', '0-0')")
        except Exception:
            self._db.close()
            raise

    @property
    def cursor(self):
        """Last locally committed scan position; never a Redis consumer cursor."""
        return self._db.execute("SELECT value FROM metadata WHERE key='cursor'").fetchone()[0]

    def _validate(self, envelope):
        if type(envelope) is not dict:
            raise ValidationError("KLP envelope must be an object")
        encoded = _json(envelope)
        try:
            if len(encoded.encode("utf-8")) > self._max_bytes:
                raise ValidationError("payload byte limit exceeded")
        except UnicodeError as exc:
            raise ValidationError("invalid Unicode payload") from exc
        for key, value in self._identity.items():
            if type(envelope.get(key)) is not type(value) or envelope.get(key) != value:
                raise ValidationError("identity binding mismatch: " + key)
        for field in ("message_id", "unit_id", "from", "to", "kind", "correlation_id"):
            _text(envelope.get(field), token=True)
        if envelope["kind"] not in KIND_MAP:
            raise ValidationError("unsupported KLP kind")
        for field in ("in_reply_to", "capability_report_ref"):
            if field not in envelope:
                raise ValidationError("missing optional-valued field: " + field)
            if envelope[field] is not None:
                _text(envelope[field], limit=1024, token=True)
        for field in ("affected_capabilities", "evidence_refs"):
            values = envelope.get(field)
            if type(values) is not list or len(values) > 64:
                raise ValidationError("invalid reference list")
            for value in values:
                _text(value, limit=1024, token=True)
        _text(envelope.get("summary"), limit=2048)
        try:
            stamp = datetime.fromisoformat(_text(envelope.get("timestamp"), limit=64).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("timezone required")
            age = (datetime.now(timezone.utc) - stamp).total_seconds()
            if age > self._max_age or age < -300:
                raise ValueError("stale or future timestamp")
        except (ValueError, OverflowError) as exc:
            raise ValidationError("invalid or stale timestamp") from exc
        return encoded

    def publish(self, envelope):
        """Validate and publish the full envelope as payload; return stream ID.

        No outgoing queue/retry or delivery promise. Retrying the same message_id
        is permitted; the receiving adapter suppresses identical duplicates.
        """
        encoded = self._validate(envelope)
        envelope = json.loads(encoded)
        if envelope["from"] != self._agent or envelope["to"] not in self._recipients:
            raise ValidationError("outbound sender/recipient not allowed")
        return self.transport.publish(sender=self._agent, to=envelope["to"],
                                      kind=KIND_MAP[envelope["kind"]], payload_dict=envelope,
                                      correlation_id=envelope["correlation_id"],
                                      in_reply_to=envelope["in_reply_to"])

    def _check_cursor(self, cursor):
        if cursor != "0-0" and self.transport.read_entry(cursor) is None:
            raise CursorTrimmedError("saved cursor absent; durable-record reconciliation required")

    def poll(self, *, batch_size=100):
        """Scan at most batch_size entries, then return up to that many pending.

        Each receipt and its cursor commit atomically before anything is returned.
        A later bad entry can raise after earlier entries committed; pending()
        recovers those entries. No saved cursor means start at earliest retained
        entry, not a claim of stream completeness. A missing saved cursor stops
        before scanning, including when local pending receipts exist.
        """
        _batch(batch_size)
        cursor = self.cursor
        self._check_cursor(cursor)
        entries = self.transport.read_since(cursor, count=batch_size)
        self._check_cursor(cursor)  # Also catch trimming during the read itself.
        for entry in entries[:batch_size]:
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not re.fullmatch(r"[0-9]+-[0-9]+", entry_id):
                raise ValidationError("invalid stream entry ID")
            if tuple(map(int, entry_id.split("-"))) <= tuple(map(int, cursor.split("-"))):
                raise ValidationError("non-increasing stream entry ID")
            encoded = None
            if entry.get("to") == self._agent and entry.get("from") in self._senders:
                if "payload_error" in entry:
                    raise ValidationError("malformed Semio payload")
                envelope = entry.get("payload")
                encoded = self._validate(envelope)
                if (entry.get("v") != "1" or entry.get("from") != envelope["from"]
                        or entry.get("to") != envelope["to"]
                        or entry.get("kind") != KIND_MAP[envelope["kind"]]
                        or entry.get("correlation_id") != envelope["correlation_id"]
                        or entry.get("in_reply_to", "") != (envelope["in_reply_to"] or "")):
                    raise ValidationError("outer Semio envelope mismatch")
            with self._db:
                if encoded is not None:
                    prior = self._db.execute("SELECT envelope FROM inbox WHERE message_id=?",
                                             (envelope["message_id"],)).fetchone()
                    if prior is not None and prior[0] != encoded:
                        raise ConflictError("conflicting message_id; reconcile durable records")
                    self._db.execute("INSERT OR IGNORE INTO inbox "
                                     "(message_id,envelope,entry_id) VALUES (?,?,?)",
                                     (envelope["message_id"], encoded, entry_id))
                self._db.execute("UPDATE metadata SET value=? WHERE key='cursor'", (entry_id,))
            cursor = entry_id
        return self.pending(limit=batch_size)

    def pending(self, *, limit=100):
        """Read committed, undelivered envelopes in receipt order, without transport."""
        rows = self._db.execute("SELECT envelope FROM inbox WHERE delivered=0 ORDER BY rowid LIMIT ?",
                                (_batch(limit),))
        return [json.loads(row[0]) for row in rows]

    def mark_delivered(self, message_id):
        """Idempotently confirm a local receipt; unknown IDs raise KeyError.

        No wire ACK is sent, no inbox record is deleted, and no job is executed.
        """
        _text(message_id, token=True)
        with self._db:
            result = self._db.execute("UPDATE inbox SET delivered=1 WHERE message_id=?", (message_id,))
            if result.rowcount == 0:
                raise KeyError(message_id)

    def wait(self, *, timeout, batch_size=100, poll_interval=0.1):
        """Poll mechanically until pending or deadline; timeout=0 performs one scan.

        Transport calls must have host-configured timeouts. Pending receipts may
        predate max_age_seconds: freshness is checked on ingestion, not replay.
        """
        deadline = time.monotonic() + _seconds(timeout)
        _seconds(poll_interval, positive=True)
        _batch(batch_size)
        while True:
            pending = self.poll(batch_size=batch_size)
            remaining = deadline - time.monotonic()
            if pending or remaining <= 0:
                return pending
            time.sleep(min(poll_interval, remaining))

    def close(self):
        """Close the local inbox (idempotent); transport lifetime belongs to host."""
        self._db.close()
