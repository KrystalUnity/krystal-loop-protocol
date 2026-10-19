"""Default-off, one-job wake bridge for an injected SemioAdapter.

Messages are notifications, not authority. A trusted host approves the trigger,
job hash, callback and budgets locally. No bus data reaches execute(). This
module starts no processes, connects to no services, and makes no model calls.
Keep the receipt database: deleting it removes the at-most-one-attempt guard.
"""
from datetime import datetime
import json
import math
import re
import sqlite3
import time

REQUIRED_TRIGGER = {"protocol", "mission_id", "mission_revision", "mission_hash",
                    "task_id", "contract_id", "contract_revision", "artifact_revision",
                    "unit_id", "from", "to", "message_id", "kind"}


class ConfigurationError(ValueError):
    """Invalid local plan, limits, or changed receipt configuration."""


class TriggerError(ValueError):
    """Pending notification does not match the approved trigger or freshness."""


class ExpiredError(RuntimeError):
    """Local authorization expired; no new callback may start."""


class AlreadyAttemptedError(RuntimeError):
    """Job was claimed previously; reconcile it, never automatically retry."""


def _json(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ConfigurationError("plan must be finite JSON") from exc


def _seconds(value, *, positive=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigurationError("duration must be finite")
    if value < 0 or (positive and value == 0):
        raise ConfigurationError("invalid duration")
    return value


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("timezone required")
        return parsed.timestamp()
    except (AttributeError, TypeError, ValueError, OverflowError) as exc:
        raise ConfigurationError("expected timezone-aware ISO timestamp") from exc


class WakeRunner:
    """One locally approved job, one durable attempt, one consumer per adapter.

    trigger is copied and all supplied fields are exact-matched, including the
    REQUIRED_TRIGGER fields. job_hash must be a SHA-256 hex digest (optional
    sha256: prefix) of the host-reviewed launcher, prompt, permissions and plan.
    This module cannot attest that hash: the host verifies mutable executable
    and prompt bytes again inside execute(), before launching anything.

    execute() takes NO arguments, returns None on successful exit, and raises
    on failure. The host MUST enforce runner_timeout_seconds, terminate/reap
    its process group on timeout, and bound adapter/socket calls. Python cannot
    preempt these synchronous callbacks; elapsed-time checking is diagnostic.
    expires_at is the latest permitted launch time, not a process kill deadline.

    wait_for_event(cursor, seconds) waits at most seconds using the captured
    cursor (never '$'); its return value is ignored. It must not execute jobs.
    Poll/event modes share the same immutable job configuration. Call counts
    are per instance, not Redis command counts or token measurements.
    """

    def __init__(self, adapter, db_path, *, trigger, job_id, job_hash, expires_at,
                 execute, runner_timeout_seconds, wait_for_event=None,
                 max_age_seconds=86400, monotonic=time.monotonic,
                 wall_time=time.time, sleep=time.sleep):
        if type(trigger) is not dict or not REQUIRED_TRIGGER <= trigger.keys():
            raise ConfigurationError("full exact trigger required")
        for key, value in trigger.items():
            if not isinstance(key, str):
                raise ConfigurationError("trigger keys must be strings")
            if key in ("mission_revision", "contract_revision"):
                if type(value) is not int or value < 1:
                    raise ConfigurationError("revision must be a positive integer")
            elif key in REQUIRED_TRIGGER:
                if not isinstance(value, str) or not value or len(value) > 256:
                    raise ConfigurationError("invalid trigger identifier")
                if any(ch.isspace() for ch in value) or value == "*":
                    raise ConfigurationError("trigger must use explicit identifiers")
        if trigger["protocol"] != "klp-core/v0.3" or trigger["kind"] not in {
                "status", "question", "answer", "handover", "finding", "stop"}:
            raise ConfigurationError("unsupported protocol or kind")
        for digest in (job_hash, trigger["mission_hash"]):
            if not isinstance(digest, str) or not re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", digest):
                raise ConfigurationError("expected SHA-256 digest")
        if not isinstance(job_id, str) or not job_id.strip() or len(job_id) > 256:
            raise ConfigurationError("invalid stable job_id")
        encoded_trigger = _json(trigger)
        if len(encoded_trigger) > 16384:
            raise ConfigurationError("trigger too large")
        self._trigger = json.loads(encoded_trigger)
        self._expiry = _timestamp(expires_at)
        self._runner_timeout = _seconds(runner_timeout_seconds, positive=True)
        self._max_age = _seconds(max_age_seconds, positive=True)
        if not all(callable(fn) for fn in (execute, monotonic, wall_time, sleep)):
            raise ConfigurationError("host callbacks must be callable")
        if wait_for_event is not None and not callable(wait_for_event):
            raise ConfigurationError("invalid event wait callback")
        self._adapter, self._execute, self._wait = adapter, execute, wait_for_event
        self._mono, self._wall, self._sleep = monotonic, wall_time, sleep
        self.counters = dict(scan_calls=0, event_wait_calls=0, poll_wait_calls=0, execute_calls=0)
        config = _json(dict(version=1, trigger=self._trigger, job_id=job_id, job_hash=job_hash,
                            expires_at=expires_at, runner_timeout_seconds=runner_timeout_seconds,
                            max_age_seconds=max_age_seconds))
        self._db = sqlite3.connect(db_path, timeout=2)
        try:
            self._db.execute("PRAGMA synchronous=FULL")
            with self._db:
                self._db.execute("CREATE TABLE IF NOT EXISTS job "
                                 "(singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                                 "config TEXT NOT NULL, state TEXT NOT NULL)")
                self._db.execute("INSERT OR IGNORE INTO job VALUES (1, ?, 'ready')", (config,))
                if self._db.execute("SELECT config FROM job WHERE singleton=1").fetchone()[0] != config:
                    raise ConfigurationError("receipt pinned to a different local plan")
        except BaseException:
            self._db.close()
            raise

    @property
    def state(self):
        """Durable ready/claimed/completed/failed; claimed means uncertain on reopen."""
        return self._db.execute("SELECT state FROM job WHERE singleton=1").fetchone()[0]

    def _eligible(self):
        if self.state != "ready":
            raise AlreadyAttemptedError("job already attempted; reconcile durable receipt")
        if self._wall() >= self._expiry:
            raise ExpiredError("local job has expired")

    def _validate(self, message):
        if type(message) is not dict:
            raise TriggerError("notification must be an object")
        for key, value in self._trigger.items():
            if key not in message or _json(message[key]) != _json(value):
                raise TriggerError("notification differs from approved trigger: " + key)
        try:
            age = self._wall() - _timestamp(message.get("timestamp"))
        except ConfigurationError as exc:
            raise TriggerError("invalid notification timestamp") from exc
        if age > self._max_age or age < -300:
            raise TriggerError("stale or future notification")

    def _dispatch(self):
        # SQLite's conditional update arbitrates the claim before host side effects.
        with self._db:
            self._eligible()
            claimed = self._db.execute("UPDATE job SET state='claimed' "
                                       "WHERE singleton=1 AND state='ready'")
            if claimed.rowcount != 1:
                raise AlreadyAttemptedError("job claimed by another runner")
        started = self._mono()
        self.counters["execute_calls"] += 1
        try:
            result = self._execute()
            if self._mono() - started > self._runner_timeout:
                raise TimeoutError("host callback exceeded declared runner timeout")
            if result is not None:
                raise RuntimeError("execute must return None on success or raise on failure")
        except Exception:
            with self._db:
                self._db.execute("UPDATE job SET state='failed' WHERE singleton=1")
            raise
        # BaseException/process death leaves 'claimed', deliberately not retryable.
        with self._db:
            self._db.execute("UPDATE job SET state='completed' WHERE singleton=1")
        self._adapter.mark_delivered(self._trigger["message_id"])
        return "completed"

    def run(self, *, armed=False, timeout, mode="event", poll_interval=0.1, batch_size=100):
        """Run a finite wait for one job; default off, with no persistent arming.

        Returns disabled, idle, or completed (successful exit, NOT acceptance).
        Existing claimed/failed/completed receipts raise AlreadyAttemptedError.
        Adapter and callback errors propagate. All messages returned in a scan
        are checked before claiming; a mismatch executes nothing. Other pending
        batches are not certified. Use a dedicated adapter inbox for this job.
        timeout bounds the wait loop, plus host-bounded calls and launcher time;
        timeout=0 performs one scan. Expiry is checked again before the claim.
        """
        _seconds(timeout)
        _seconds(poll_interval, positive=True)
        if type(armed) is not bool or mode not in ("poll", "event"):
            raise ConfigurationError("explicit boolean arming and poll/event mode required")
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ConfigurationError("batch_size must be 1..1000")
        if not armed:
            return "disabled"
        if mode == "event" and self._wait is None:
            raise ConfigurationError("event mode requires wait_for_event")
        deadline = self._mono() + timeout
        while True:
            self._eligible()
            self.counters["scan_calls"] += 1
            messages = self._adapter.poll(batch_size=batch_size)
            cursor = self._adapter.cursor
            for message in messages:
                self._validate(message)
            if messages:
                return self._dispatch()
            remaining = min(deadline - self._mono(), self._expiry - self._wall())
            if remaining <= 0:
                self._eligible()
                return "idle"
            if mode == "event":
                self.counters["event_wait_calls"] += 1
                self._wait(cursor, remaining)
            else:
                self.counters["poll_wait_calls"] += 1
                self._sleep(min(poll_interval, remaining))

    def close(self):
        """Close only the job receipt; the host owns adapter and callback lifetimes."""
        self._db.close()
