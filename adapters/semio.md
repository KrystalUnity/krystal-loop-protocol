# Optional Semio Coordination Adapter

**Status:** reference integration, not a KLP Core requirement.

## In Plain English

Let agents leave each other short, addressed messages instead of repeatedly
asking for updates or copying entire conversations. A worker says where its
finished work and checks can be found. A critic reviews that exact work. The
coordinator decides what happens next under the agreed task limits.

The message is a notification, not permission and not proof that the work is
correct. Your existing files, task records and evidence remain the source of
truth. KLP still works without this adapter.

## What Is Included

The [Python example](../examples/semio-coordination/README.md) maps KLP
coordination envelopes onto a Semio-compatible stream interface, with a local
durable inbox, duplicate handling, revision checks and finite mechanical waits.
Offline tests require only Python's standard library. Live transport is supplied
by the host; the example does not bundle private platform code or credentials.

The base adapter has no agent launcher, model router, acceptance engine or
production deployment. The optional one-job wake bridge in the
[Python example](../examples/semio-coordination/README.md#one-job-wake-bridge)
can call a host-registered launcher after the exact expected notification.
The job is approved and fixed locally before arming; no command or prompt comes
from the bus. This is not an installed daemon or automatic desktop integration.

## Keep Three Things Separate

| Layer | Responsibility |
| --- | --- |
| KLP records | Mission, specifications, task boundaries, workflow state, evidence, findings and decisions. |
| Semio transport | Compact addressed notifications with exact identities and evidence references. |
| Host runner | Deliver notifications to authorized sessions and enforce execution limits. |

KLP can require content constraints in a task specification. It does not store
or govern an application's domain data automatically. Neither the adapter nor
an agent message may amend the mission or authorize a consequential action.

## Interoperability

Keep the complete KLP envelope in the Semio `payload`. Preserve mission ID,
revision and hash, task and contract identity, artifact revision, sender,
recipient, correlation and evidence references. Use the existing Semio outer
kinds: KLP `handover` maps to `propose`; `finding` and `stop` map to `alert`.
The original KLP kind remains inside the payload.

Use an explicit per-task sender/recipient configuration. Names and hashes are
consistency checks, not authentication. The host must secure its Redis endpoint
and local files; a party with write access can impersonate a sender. References
are untrusted data: the adapter does not fetch URLs, open referenced files or
follow instructions from them.

## Recovery and Limits

- Receiving a notification is not accepting a worker result. A delivery ACK
  is not a critic PASS, and a PASS is not deployment authority.
- The local inbox is delivery bookkeeping, not the KLP state-event ledger.
  Keep task decisions and evidence in durable records outside the stream.
- Reusing a message ID for different content is an error, not an update.
- Pending notifications survive receiver reopening until explicitly marked
  delivered. This is not exactly-once job execution; the host must also dedupe
  work using task/unit/artifact identity.
- If stream retention has removed the saved cursor, stop and reconcile against
  durable records. Do not silently reset to the newest message.
- A new receiver has no proof of events lost before it first joined. Bootstrap
  it from durable task records. Use one inbox per task binding and agent.
- This example supports one reader process per inbox, not a distributed worker
  queue. It provides no HA, broker authentication or automatic supervision.
- Payload limits constrain volume, not secrets. Send only reviewed summaries
  and references; never raw credentials, customer data or private transcripts.

## Bounded Adoption

Start with one worker, one independent read-only critic and a coordinator.
Record the exact candidate, deterministic checks and critic findings. Test
delivery, duplicates, stale revisions and recovery before relying on it.
Measure notification sizes, handover delays and idle model calls. Do not claim
token or cost savings without a comparable baseline and actual measurements.

The protocol and record format are unchanged. Other transports and harnesses
can implement the same optional mapping without adopting a KU installation.

## Measuring a Wake Integration

Compare the same workload, delay, runner, prompt and candidate. Count actual
transport reads, blocking waits, launches, delivered bytes and available model
usage separately. A mechanical polling loop already makes no model calls;
replacing it with a blocking wait does not itself reduce model context.
Report zero observed prompt savings when both paths use the same prompt. Any
comparison with repeated LLM-driven status checks needs a real separate
baseline, not an assumed one. Keep failed launches in the denominator.
