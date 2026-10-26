# Choose the Right Amount of KLP

Use **Standard** for ordinary bounded work. Use **Critical** when a mistake
could change the product's essential behavior, lose durable data or cross a trust
boundary. Routine release permission is a separate gate, not automatically a
Critical task. Keep the proof; cut repeated administration.

These execution profiles are separate from the infrastructure options in
[Runtime Profiles](RUNTIME_PROFILES.md). Redis, Semio, Nexus, vector memory and
per-step messages are not prerequisites for either profile. Local platform
policies may still require a handover; reference one record instead of copying it.

New to KLP? Use the [solo-operator example](examples/solo-operator.md).
Standard/Critical chooses the required assurance; infrastructure Profiles A/B/C
choose storage and transport. You do not need to choose infrastructure beyond
Git and local files to begin either execution profile.

## Select Before Editing

The coordinator records the profile and a short reason in the task record under
operator authority or an existing standing policy. Inspect the affected behavior,
data and interfaces, not just the number of changed files. Reference the durable,
operator-approved product promise and any existing Mission Contract/trigger rules.
If no product promise or task authority exists, clarify it before implementation.

Select **Critical** for any of these triggers:

- A critical capability or existing Mission Contract trigger is affected.
- A save/schema migration, persistent-data conversion or destructive data operation.
- A security or authorization boundary, tenant isolation, secrets, money, billing
  or consequential economy change as bounded by the approved project policy below.
- A release bundle or deployment-process change affecting critical behavior,
  infrastructure, access, data conversion or production data mutations beyond an
  established, bounded release procedure. Routine releases follow the separate gate.
- A capability restriction, mission amendment, proof/control weakening or change
  to what the product is allowed to decide.
- Uncertain impact that could plausibly reach any of the above boundaries.

Examples: fixing a harmless display typo can be Standard; changing save formats,
tenant filtering or persistent rewards is Critical. Being a one-person project does not
lower the consequence of losing its players' saves.

Unknown impact is not evidence of low risk. Do a bounded scope check; if it
cannot establish eligibility for Standard, stop and prepare Critical work.
Discovery of a trigger during Standard stops the affected work before more edits.
Retain its evidence, obtain any missing authority, and establish the Critical
contract and accepted baseline before resuming. Later results cannot retroactively
substitute for the missing baseline. Never downgrade an active Critical run to
avoid a failed check, blocked review, exhausted budget or missing capability proof.

### Project Economy Policy

Use an operator-approved, versioned project policy to define which economy
changes are consequential and any bounded Standard tuning allowance. Record its
exact reference in the task and critic packet. Persistent currency, purchases,
saves and account progression remain Critical when their behavior or correctness
is affected. Merely displaying an unchanged, already-verified value is assessed
against the actual behavior and existing mission triggers, not the screen name.

Temporary in-run tuning may be Standard only inside explicit policy bounds, with
relevant executed probes and no other Critical trigger. Check indirect persistent
effects: a temporary damage bonus that changes banked rewards is not automatically
transient. Policy should state the tunable values/ranges, excluded effects and
required checks; it cannot override a Mission Contract trigger or authorize a live
action. Missing policy or uncertain effects are not permission to assume low risk.

### Author Behavior-Based Mission Triggers

Prefer protected behavior or claims over whole-file triggers. For example,
"changes to the calculation, source or meaning of displayed persistent balances"
is more precise than "all panels in menu.mjs". A new copy-only panel need not
affect that capability, while a formatter or API change elsewhere might.

Use paths and symbols as discovery clues alongside data flow, user-visible claims
and observable effects. Never use a path mismatch as proof that behavior is safe.
Distinguish a text/layout change from a change to what the UI promises about state.
The critic must check the actual behavior, not just accept a copy-only label.

An existing whole-file trigger remains binding. Narrowing it requires the normal
operator-approved Mission Amendment Request, with technical explanation and a
plain-English impact statement. Do not reinterpret, relabel or bypass it mid-run
to obtain Standard eligibility. Existing Critical runs retain their agreed gates.

## Standard: One Record, One Review Plan

Record identity: **`klp-standard/v0.1`**. This is a documentation-level profile,
not a claim of Core v0.3 conformance. Its compact record can be a versioned issue
or one Markdown file using the [Standard task template](examples/standard-task.md).

1. Record the authorized outcome, product-promise reference, profile reason,
   concrete edit boundary, protected paths, checks, roles and finite limits.
2. Identify the exact base artifact. For a regression, demonstrate the relevant
   failure when practical; otherwise retain direct evidence explaining it.
3. Implement inside the boundary and run the declared checks with observable
   expected results. A required check that did not run is not a pass.
4. Obtain one independent critic pass on the exact candidate, including the
   relevant source context and check evidence. In that same critic pass, confirm
   Standard eligibility against the actual changed behavior, project policy and
   Mission Contract triggers. The worker cannot self-review.
5. Adjudicate findings with evidence. Repair only confirmed blockers within the
   declared budget, rerun affected checks and obtain targeted review of the new
   candidate where needed to close those blockers. Every accepted candidate
   needs review applicable to its exact contents; stale verdicts do not carry over.
6. Check the integrated artifact, record final findings, limitations and measured
   effort, then finish. If integration changes the reviewed contents, recheck
   affected behavior and review that delta; do not silently accept a new artifact.

Record the critic's `profile_assessment` as `eligible`, `critical_trigger` or
`insufficient_evidence`, with the exact candidate, policy/mission references and
supporting evidence. Missing or unresolved profile assessment blocks Standard
acceptance. A `critical_trigger` stops affected Standard work under the escalation
rule above; a disagreement is evidence-adjudicated, not overridden by a coordinator
label. Correct demonstrably false findings using the existing disposition process;
genuine unknowns stay unresolved. Refresh the assessment for changed final contents.

Use an exact Git revision, immutable snapshot or content digest for artifacts
and a versioned task record for authority. A commit label alone does not identify
dirty working files. No extra per-file hash manifest or mission-hash ceremony is
required by Standard, but an existing Mission Contract must not be ignored.

The worker may also coordinate and run checks, but cannot be its own critic.
Use a fresh, read-only critic identity; different-family criticism is preferred.
Disclose same-family review as such, not as different-family independence. A
project's stricter independence policy still applies. This does not relax the
included critic harness's explicit family checks.

One task record can hold the assignment, factual handover, finding decisions
and final receipt. Preserve prior revisions through ordinary version history;
do not overwrite evidence to make failed work disappear. No per-step message,
separate JSONL state ledger, new database, stamping utility or additional auditor
seat is required by Standard. Do not build a stamping tool just to run the task.

One review plan is the default, not one review regardless of what it finds.
Further review must close a named blocker, cover changed integration or resolve
a specific missing required proof. Advisory notes do not start another loop.
Keep planning, checks, reviews, repairs, waiting and documentation within one
finite time/cost/repair budget. Report unavailable usage as unknown, not zero.

## Critical: Preserve the Existing Core Gate

Record identity: **`klp-core/v0.3`**. Follow [Core Protocol](PROTOCOL.md) in full:
mission binding and immutable identity, accepted pre-work capability baseline,
separate critical roles, bounded implementation, deterministic checks, independent
criticism, finding adjudication, integrated-artifact capability proof and durable
lifecycle evidence. Records may be combined, but required facts cannot be omitted.

Critical also has a stopping point. Reuse valid evidence tied to the right
artifact instead of commissioning another review of the same facts. Do not
invent extra approval clicks or require zero advisory findings.

The current Core validators, lifecycle fixtures, worker/critic packet examples
and Semio envelope examples retain their stated record versions. They do not
validate or automatically execute Standard. Do not pass a Standard record to a
Core-only validator or adapter and claim success. A host using Standard needs
an explicitly compatible integration; none is added by this documentation change.

## Routine Release Gate

Shipping a Standard change through an established, operator-approved release
procedure does not automatically make it Critical. Release qualification for
such a change is this gate; implementation profile and live-action permission
remain separate. No profile or passing gate is deployment authority.

Before release, record in the existing task or release record:

1. The exact release artifact and destination, with the entire release bundle
   compared to the deployed baseline. Check combined changes and the release
   procedure for Critical triggers, not just the last Standard task. If a trigger
   is found, stop release and establish the applicable Core authority, accepted
   baseline and proofs. Do not use release checks to retroactively invent them.
2. Relevant lasting product probes and integration checks actually executed
   against that artifact, with assertions, results and evidence. Reuse fresh
   evidence that matches the same artifact, scope and environment; do not add a
   duplicate critic call merely because a release follows. Required missing,
   failed or inconclusive proof blocks release.
3. An applicable rollback path and retained prior artifact/data recovery evidence
   appropriate to the risk. A migration or irreversible change is not routine
   merely because a deployment script can run it.
4. Explicit operator authorization for the artifact/destination or a documented
   standing release delegation covering it. KLP records that authority; the
   gate is not deployment authority. If authorization is pending, report
   `ready_for_authority_decision` and do not deploy.
5. Bounded post-release checks of the deployed artifact and required behavior,
   with failure/rollback conditions and who is authorized to act. Do not claim
   live success from a pre-release pass. If activation cannot be verified,
   report it as unverified and follow the approved stop/recovery procedure.

If integration, configuration or build changes the artifact or assessed effects,
refresh affected checks and profile/review evidence before proceeding. A bundle
containing Critical work retains that work's required Core gate; it cannot be
reclassified by packaging it with Standard changes. Existing Critical runs retain
their requirements; this release gate is not a downgrade mechanism.

## Small Related Edits Without Scope Drift

Both profiles may use an **upfront, pre-authorized adjacent-edit allowance**.
It must name a narrow directory or enumerated candidate set, the permitted kind
of edit, a maximum additional-file count, protected paths and excluded actions.
An exact list with no allowance remains exact. "Anything related" is not a bound.

Before using the allowance, the coordinator records the added file, why it is
necessary, its relationship to the unchanged outcome, affected checks and the
remaining allowance. Check profile triggers again. The worker does not enlarge
its own authority. No task revision or operator click is needed when this is
already delegated; the record shows an exercise of existing authority.

Anything outside that allowance, or changing mission, acceptance criteria,
security, external side effects, dependencies or budget, still stops for the
applicable authority decision. Test-isolation changes can touch security/data
boundaries: an apparently small edit is not automatically eligible.

## Review Findings Without Invented Requirements

Keep truth (`confirmed`, `refuted`, `unresolved`) separate from blocking status.
For each proposed condition, name the actual task commitment or required proof.
A reviewer preference is advisory, not a new acceptance condition. A confirmed
failure within supported conditions that violates a commitment still blocks.
An unresolved required proof is not converted into an advisory to finish faster.

For example, a reviewer may ask for a different simulation hash after a change.
If the bot demonstrably never reaches the changed behavior, a changed hash is
not valid evidence of that behavior. Refute the demand with source/trace evidence,
then verify the actual task outcome with a suitable existing probe or a bounded
test. Do not claim the unreachable simulation proved the new feature.

## Tests and Timeouts

Keep lasting product probes in the owning project. Choose relevant checks for
the task and release risk; KLP does not prescribe one game's browser/simulation
suite for every project. Follow [test isolation](SAFETY_AND_LIMITS.md#offline-test-boundary).
Do not let a skipped assertion, empty result or inherited provider key turn a
test into a false pass or an accidental external call.

Prefer compact, sufficient critic context over a large diff dump. Set a finite
provider-specific timeout inside the parent budget. A timeout is an incomplete
review; any retry consumes the same budget and must be delegated. Increasing
every timeout to 800 seconds is not a protocol requirement or an efficiency fix.
