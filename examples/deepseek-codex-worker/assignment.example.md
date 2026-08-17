# Bounded Worker Assignment

- Task ID: `example-normalize-title`
- Base revision: `controller-supplied-base-revision`
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

Return only a factual handover matching `expected-handover.json`. Do not issue a
PASS verdict and do not commit the result.
