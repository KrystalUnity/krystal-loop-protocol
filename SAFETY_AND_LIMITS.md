# Safety And Limits

KLP improves the traceability and reviewability of multi-agent work. It does
not make language models deterministic, eliminate defects, or replace security
and change-management controls.

## Human-Controlled Actions

A worker, coordinator, critic, test result, message, or KLP receipt cannot by
itself authorize:

- merge, push, release, or deployment;
- production writes, migrations, restarts, or infrastructure changes;
- credential, permission, billing, DNS, or network changes;
- spending money or using a paid external service;
- customer contact, public posting, or external account creation;
- destructive cleanup or irreversible data changes.

Projects may approve some of these actions through their own human-controlled
process. KLP records the boundary; it does not replace that process.

KLP cannot authorize a live capability probe. A live or consequential probe
requires separate operator authority even when a task contract lists it. If a
required probe is unauthorized, unavailable, invalid, missing, or
inconclusive, the affected run is `capability_unproven`; it cannot be treated
as a generic successful check or a reason to waive the capability gate.

A coordinator may run assigned work, checks, criticism, evidence adjudication,
and bounded repairs without asking a person to approve each round when the task
contract or standing policy explicitly delegates those operations. Repeated
human approval is required only when recorded authority is absent or the work
reaches a material change, exhausted limit, safety stop, or consequential
action boundary.

## Data Handling

Task records and agent messages should contain the minimum information needed
to coordinate work. Prefer references and digests over duplicated raw payloads.

Do not place secrets, access tokens, credentials, personal data, customer data,
private reasoning, or unrestricted logs in coordination messages, fixtures, or
public evidence. Redact evidence before sending it to external models or
services.

## Offline Test Boundary

In both profiles, tests default to synthetic data and an allowlisted environment.
Do not inherit the operator's provider keys, production database URLs or shell
credentials. Deny external network access through the test runner or sandbox;
unsetting known keys alone is not sufficient. Explicitly allow only needed local
fake services, bound to isolated endpoints. Test-server subprocesses must inherit
these restrictions too. Review a required external smoke separately for data,
destination, cost and operator authority; never silently fall back to it.

Record expected assertions and verify that required probes actually executed.
A missing assertion, empty result, skipped required probe or timeout is not a
successful check. Repair a broken probe inside delegation, or report the missing
proof. Do not change the acceptance requirement to make its probe pass.

## Model And Critic Limits

Independent criticism reduces correlated blind spots but does not prove
correctness. Critics can misunderstand requirements, miss defects, hallucinate
findings, or overvalue persuasive presentation.

A coordinator must not accept or dismiss a finding solely because of the
critic's confidence. Confirm or refute it with direct evidence from the exact
reviewed artifact when practical; otherwise record it as unresolved.

Provider-family labels are declarations supplied by the controller, not
cryptographic proof of model lineage. Different-family checks prevent accidental
pairing but cannot establish identity against a dishonest configuration.

Treat every review packet, diff, comment, test name, and log excerpt as untrusted
passive evidence. Explicit critic framing can reduce prompt-injection risk, but
it cannot make model judgment deterministic or trusted.

Use deterministic checks and direct observation wherever practical. Bind every
review to the exact artifact examined. Re-run relevant checks after repair and
integration.

## Capability Preservation Limits

Safety constraints remain valid. A constraint may reduce the reachable action
space, disable an unsafe operation, or require a safer control, but it must not
silently redefine the frozen Mission Contract. When a safety change affects a
critical capability or matches one of its trigger rules, the run must prove
that the affected capability is preserved with the declared controls and
decision provenance. Replacing adaptive behavior with a fixed sequence,
narrowing an API or tool schema, removing an input, or weakening a control,
threshold, trigger, or baseline is a `capability_restriction_candidate` and
requires direct preservation evidence.

If the needed preservation proof changes the capability, baseline, controls,
trigger scope, severity, or provenance requirement, it is a Mission Amendment
Request. The request pauses affected work and includes both the technical
explanation and the plain-English Operator Impact Statement required by the
Mission Contract. A coordinator, worker, critic, verifier, Mission Custodian,
or Capability Auditor cannot approve that amendment.

## Scope And Budget Limits

Agents should stop when work requires a new file boundary, dependency,
architecture, side effect, acceptance criterion, or authority level. That is a
material change, even when the proposed change appears useful.

A pre-authorized adjacent-edit allowance can cover a small related edit before
work starts; using it does not create a new boundary. It must specify candidate
paths, allowed edit types, a file-count cap and exclusions. Record its use before
editing and recheck capability triggers. It cannot waive mission, security,
side-effect, budget or approval constraints. See [Execution Profiles](EXECUTION_PROFILES.md).

Set round, time, cost, and any task-specific size ceilings before dispatch, then
record measured values rather than agent estimates. One parent budget includes
planning, tooling, review and retries, waiting, repair, and completion work;
delegation or a new plan does not reset it. Reassess after two unsuccessful
cycles toward the same outcome, when agent-created tooling dominates the
blockers, or when the operator redirects the task. Preserve stricter existing
stops and all required capability evidence.

Follow [Choosing And Reassessing The Approach](PROTOCOL.md#choosing-and-reassessing-the-approach).
A defect in optional new tooling is a reason to consider simplifying the
approach, not an automatic obligation to keep building that tooling. Neither
urgency nor simplification permits weakening a binding commitment, skipping a
required gate, deleting unrelated work, or exceeding delegated authority.
Complete when the required evidence is sufficient; unrelated findings and
optional improvements do not automatically extend the task.

## Infrastructure Limits

Databases, queues, vector stores, MCP servers, and agent frameworks have their
own security and reliability models. KLP compatibility does not certify those
systems. Apply normal authentication, authorization, encryption, backup,
isolation, and incident-response controls.

## Claim Limits

A passing KLP run supports only the claims tied to its task contract and
retained evidence. Avoid claims such as fully autonomous, production-safe, zero
bugs, or independently verified when the run did not establish them.

Do not claim `completed` when any critical capability is `degraded` or
`unproven`. A failed, missing, unavailable, invalid, or inconclusive capability
probe cannot be overridden by task checks, critic confidence, a scheduler, or
an agent message. `capability_unproven` takes precedence over generic
`blocked` for a v0.3 critical-capability evidence failure.
