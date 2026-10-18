# Semio Coordination Example

This optional adapter carries KLP notifications over a host-supplied Semio
transport. It does not install or require a particular agent framework. Read
the [adapter boundary](../../adapters/semio.md) before connecting a live bus.

## Run Offline Checks

From the repository root, with Python 3.12 or newer:

```bash
python3 -m unittest discover -s examples/semio-coordination/tests -v
```

These tests use a fake transport and temporary local inboxes. They do not call
a model, require Redis, contact a provider or alter a running service.

## Host Transport Contract

Supply an object with these methods:

```python
publish(*, sender, to, kind, payload_dict, correlation_id=None,
        in_reply_to=None, nexus_ref=None) -> str
read_since(last_id="0-0", count=100) -> list[dict]
read_entry(entry_id) -> dict | None
```

`publish` returns a stream entry ID. `read_since` returns oldest-first entries
strictly after the supplied ID. Each decoded entry has `id`, `v`, `from`, `to`,
`kind`, `correlation_id`, `in_reply_to`, `nexus_ref`, `payload` and `ts`.
`payload` is a JSON object; malformed decoding should be represented as
`payload_error`. `read_entry` returns `None` if an entry was removed.

The KU `CoordStream` helper implements this interface. It is a host capability,
not included in this public repo; other installations may supply their own
compatible implementation. No KU module is imported by the adapter itself.
The host must bound network connect/read calls: a finite adapter wait cannot
interrupt a blocked transport call. Configure socket timeouts and bounded
retries before using a live Redis client.

## Connect an Existing Runner

Add this example directory to your runner's Python import path. The runner
supplies `transport`, a private `inbox_path`, and an exact `identity` recovered
from durable task records, not from the incoming message:

```python
from semio_adapter import SemioAdapter

identity = {
    "protocol": "klp-core/v0.3",
    "mission_id": mission_id,
    "mission_revision": mission_revision,
    "mission_hash": mission_hash,  # lowercase SHA-256; optional sha256: prefix
    "task_id": task_id,
    "contract_id": contract_id,
    "contract_revision": contract_revision,
    "artifact_revision": exact_candidate_digest,
}
inbox = SemioAdapter(
    transport, inbox_path, identity=identity, agent="coordinator",
    allowed_senders={"worker", "critic"},
    allowed_recipients={"worker", "critic"},
)
try:
    notifications = inbox.wait(timeout=10, batch_size=100, poll_interval=0.5)
    for notification in notifications:
        # Host-defined durable receipt, NOT execution or artifact acceptance.
        record_notification(notification)
        inbox.mark_delivered(notification["message_id"])
finally:
    inbox.close()
```

The variables and `record_notification` are supplied by your host; this is an
integration sketch, not an agent-launch command. The sender uses its own adapter
instance and `publish(envelope)` with the full
[KLP coordination envelope](../../AI_AGENT_INTEGRATION.md#generic-coordination-envelope).
Preserve its ID and timestamp when retrying the same message. A new message
needs a new ID. `handover` maps to outer `propose`; `finding`/`stop` map to `alert`.

Defaults are a 16 KiB compact-JSON payload limit, 24-hour ingestion age limit,
and five minutes of future-clock tolerance. Names and revision fields are
validated, not authenticated. A late or malformed addressed message raises
`ValidationError` without skipping that entry. A conflicting duplicate raises
`ConflictError`; a missing saved cursor raises `CursorTrimmedError`. On these
errors stop the affected consumer and reconcile from durable records; do not
loop retries indefinitely or erase the inbox to silence the error. Unrelated
senders and recipients are skipped.

`pending()` reads already-stored notifications without touching the transport.
Their age is checked on ingestion, not again on replay: the host must re-check
task authority and current candidate before taking action. `mark_delivered()`
is local bookkeeping; it sends no wire ACK and does not delete dedupe records.
Any optional wire delivery ACK belongs to the host's separate receipt handling,
not this adapter's KLP message inbox. No ACK is required for the example.

## Delivery Policy

Use small reviewed summaries and durable evidence references. Every consumer
must know the exact mission, contract, task and candidate revision plus the
allowed sender and recipient identities before receiving a notification.
Create a new inbox when changing that binding; do not reuse an old inbox to
silently accept a different task or candidate.

Keep the inbox private and local. One receiver process owns each inbox. Pending
messages are repeatable after a crash; mark them delivered only after the host
has durably recorded receipt. That mark is not KLP task acceptance. Deduplicate
actual jobs separately and reconcile from durable task records after a stream
retention gap. There is no exactly-once job or reliable outbox guarantee.

No message is automatically executed. The adapter does not dereference evidence
links, launch tools, choose a model, interpret a critic verdict or grant
authority. Use it with an existing runner rather than creating a new always-on
agent just to poll for updates.
