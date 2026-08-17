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

## Data Handling

Task records and agent messages should contain the minimum information needed
to coordinate work. Prefer references and digests over duplicated raw payloads.

Do not place secrets, access tokens, credentials, personal data, customer data,
private reasoning, or unrestricted logs in coordination messages, fixtures, or
public evidence. Redact evidence before sending it to external models or
services.

## Model And Critic Limits

Independent criticism reduces correlated blind spots but does not prove
correctness. Critics can misunderstand requirements, miss defects, hallucinate
findings, or overvalue persuasive presentation.

Use deterministic checks and direct observation wherever practical. Bind every
review to the exact artifact examined. Re-run relevant checks after repair and
integration.

## Scope And Budget Limits

Agents should stop when work requires a new file boundary, dependency,
architecture, side effect, acceptance criterion, or authority level. That is a
material change, even when the proposed change appears useful.

Set round, time, and cost ceilings before dispatch. Repeated blocking findings
or no measurable evidence improvement should trigger a plateau rather than an
unbounded agent loop.

## Infrastructure Limits

Databases, queues, vector stores, MCP servers, and agent frameworks have their
own security and reliability models. KLP compatibility does not certify those
systems. Apply normal authentication, authorization, encryption, backup,
isolation, and incident-response controls.

## Claim Limits

A passing KLP run supports only the claims tied to its task contract and
retained evidence. Avoid claims such as fully autonomous, production-safe, zero
bugs, or independently verified when the run did not establish them.
