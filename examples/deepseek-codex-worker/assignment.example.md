# Bounded Worker Assignment

- Task ID: `example-normalize-title`
- Base revision: `controller-supplied-base-revision`
- Mission Contract hash: `sha256:mission-example-123`
- Affected capabilities: `title-normalization`
- Outcome: Make `normalizeTitle()` collapse repeated ASCII spaces.
- Allowed paths: `src/title.ts`, `tests/title.test.ts`
- Protected paths: every other path
- Forbidden actions: Git operations, dependency changes, network access, live
  actions, nested agents, and undeclared tests
- Deterministic check: `npm test -- tests/title.test.ts`
- Required evidence: exact command, exit status, and concise output
- Time limit: 15 minutes
- Repair limit: one implementation attempt
- Stop conditions: scope change, missing dependency, failing unrelated check,
  credential request, or inability to produce the required evidence

Return only a factual handover matching `expected-handover.json`, including
observed capability risks. Do not issue a PASS verdict, certify preservation,
pass or override the mechanical capability gate, or commit the result.
