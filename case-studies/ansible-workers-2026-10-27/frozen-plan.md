## K01 — Scope and limits

Plan a narrow source change for opt-in offline installation of **local collection tarballs using local tarballs and already installed dependencies**. Preserve existing behavior when offline mode is not requested.

- Confine implementation, fixtures, tests, and captured evidence to `/app`.
- Use only repository sources and already available dependencies. Do not consult external solutions, install dependencies, or contact external services.
- Limit the workflow to **50 minutes, $10, and at most two repair-and-retest cycles**.
- Do not introduce an installation transaction service, persistent operation IDs, a cancellation API, or unrelated public interfaces.
- Do not broaden supported CLI artifact types or redesign signature verification.

All changes and tests below are proposed. No inspection, implementation, execution, or approval is claimed.

## K02 — Inspect the relevant call graph and existing guarantees

Before editing, inspect these paths and their existing tests:

1. Collection-install parser registration and dispatch in `lib/ansible/cli/galaxy.py`.
2. `install_collections`, `download_collections`, and `_resolve_depenency_map` in the collection installation flow.
3. Resolver construction and provider behavior in `lib/ansible/galaxy/dependency_resolution/`.
4. `MultiGalaxyAPIProxy`, requirement classification, and `ConcreteArtifactsManager`.
5. Installed-candidate discovery, dependency metadata, signature handling, and source preparation.
6. Artifact-manager context ownership, extraction, destination mutation, installation metadata, and success reporting.
7. Every affected caller, positional invocation, type comment, mock, and test assertion.

Retain the existing spelling `_resolve_depenency_map`.

Answer these implementation questions before choosing guard locations:

- Can source parsing, API initialization, authentication discovery, artifact preparation, or signature handling initiate a connection before proxy version lookup?
- Which concrete-artifact types are local, and which can download or invoke Git?
- How are installed candidates supplied separately from remote candidates?
- Can local candidate processing accidentally request remote metadata or signatures?
- Is installation incremental, atomically published, or durably transactional? Include metadata written outside the collection directory.

Do not infer locality from `is_concrete_artifact`, a filename suffix, a warm cache, or a URL resolving to a local address. Do not infer durable commit from a rename, a temporary directory, or a success message.

## K03 — Implement the exact CLI and parameter contracts

### CLI option

Register `--offline` on **collection install**, using argparse `action='store_true'`, with:

| Attribute | Required value |
|---|---|
| `dest` | `offline` |
| `default` | `False` |
| Resulting `const` | `True` |

Let the `store_true` action supply its constant; do not pass an unsupported `const` argument to that action.

The stored help string must be exactly:

> Install collection artifacts (tarballs) without contacting any distribution servers. This does not apply to collections in remote Git repositories or URLs to remote tarballs.

Test the stored string directly, rather than terminal-wrapped help output. Do not add the flag to unrelated subcommands.

### Parameter propagation

Append positional-capable `offline=False` parameters to:

- `install_collections(...)`, as its **final parameter**;
- `_resolve_depenency_map(...)`, as its **final parameter**.

Forward the CLI value into `install_collections`, then the value received by that function into `_resolve_depenency_map`, and onward into resolver construction. K02 may confirm that collection installation can be reached from a parser that does not register `--offline`, such as role install or an implicit `ansible-galaxy install` whose requirements file contains collections. Wherever that is possible, read the CLI value defensively (for example `context.CLIARGS.get('offline', False)`). Those paths then forward `False` and keep their existing online behavior instead of failing on a missing argument. When the collection-install parser supplies the value, use it unchanged.

Also implement these supporting contracts:

- `download_collections(..., offline=False)` accepts the argument but calls dependency resolution with **`offline=False`**, even if its own caller passes `True`. This PR does not provide offline download behavior.
- `build_collection_dependency_resolver(..., offline=False)` forwards the supplied value to its proxy.
- `MultiGalaxyAPIProxy(..., offline=False)` retains that value.

Preserve omitted-argument callers through the false defaults. Update relevant type comments, docstrings, mocks, and positional-call expectations without reordering existing parameters.

## K04 — Enforce the proxy contract

Store offline state per proxy instance and expose a read-only property named exactly:

`is_offline_mode_requested`

It must return the retained boolean, including `is True` and `is False` behavior for boolean inputs. Supply no setter and no global mode switch.

### Version lookup

For `get_collection_versions`:

- Preserve the concrete-artifact manager’s local file/directory resolution path.
- For a non-file/non-URL collection-name requirement while offline, return an empty set of remote candidates before API iteration or connection-related work.
- Apply this to both default server selection and an explicit `GalaxyAPI` source.
- Ensure unsupported network-capable concrete sources cannot bypass offline admission checks described in K05.

Returning no remote candidates must not remove installed candidates discovered elsewhere by the resolver.

### Metadata and signatures

At the start of each method below, raise `NotImplementedError` while offline:

- `get_collection_version_metadata`
- `get_signatures`

These guards must precede API selection, token access, source recording, and remote work. They apply even when a direct caller supplies a candidate that might otherwise use cached data.

Preserve direct local dependency extraction through `get_collection_dependencies` where applicable.

### Online behavior

With `offline=False`, retain existing:

- server ordering and explicit-source behavior;
- version, metadata, and signature calls;
- artifact-source recording;
- warnings, fallback, and exception behavior.

Do not combine this change with unrelated cleanup of the proxy.

## K05 — Prevent network access throughout the supported offline flow

Proxy guards are necessary but insufficient if earlier source preparation can connect.

### Source admission

Place targeted checks before any network-capable source handler executes.

Under `--offline`:

- Admit supported local tarballs and existing installed collections.
- Preserve existing internal local-directory resolution without advertising new CLI support.
- Reject remote tarball URLs and remote Git sources before downloading, redirect handling, authentication, or Git subprocess execution.
- Apply checks to supported requirements-file inputs and any later source introduction the repository actually permits.
- Do not invent a dependency syntax merely to test a hypothetical transitive URL.
- Do not treat a cached remote source as a supported local tarball.

The help text excludes remote-source support; it is not permission to fetch those sources during an offline invocation. Without `--offline`, preserve their existing behavior.

### Candidate and dependency handling

Use existing installed-candidate discovery, collection-path precedence, version constraints, and local manifest handling.

A missing or incompatible local dependency must produce a local resolution failure. A server becoming available later must not trigger fallback.

If local candidate handling currently performs optional remote enrichment, use the proxy’s offline property to bypass only that enrichment. Do not route a valid local dependency through a method that is required to raise offline.

### Signature policy

- Do not fetch remote signatures offline.
- Preserve local integrity checks and locally satisfiable signature verification.
- Do not blanket-disable verification or turn an explicitly required signature policy into success.
- If a requested policy cannot be satisfied locally, fail clearly without connecting.
- Do not broadly catch `NotImplementedError` and reinterpret it as successful verification.

### Guard scope

Review reachable API initialization, URL opening, downloads, authentication, redirects, signatures, retries, and Git execution.

Use targeted production routing and proxy guards. Network monkeypatches belong in tests, not the implementation.

## K06 — Preserve security checks, fencing, and reference lifetimes

Offline mode must retain existing:

- archive traversal and symlink protections;
- artifact integrity checks;
- destination and filesystem permission checks;
- installed-version and force semantics;
- writer exclusion or publication fencing, if any already exists.

Do not add `--force` to recovery or replay.

Keep the artifact manager and its temporary files alive until all consumers finish resolution, verification, and installation. Do not return candidates whose backing files have already been cleaned up.

On replay:

- Run the ordinary validation and authorization path again.
- Do not reuse stale candidate maps, credentials, temporary paths, or closed handles as an authorization shortcut.
- Retain existing fences and destination checks.
- Confirm an earlier owned writer has exited before retrying or cleaning its fixture.

For a missing or unreadable local artifact, fail locally without reinterpreting it as a reason to search Galaxy.

Do not claim snapshot isolation or new concurrent-writer support. Removing a pathname after a file is opened may leave a valid readable descriptor; tests must distinguish that case from removal before opening.

## K07 — Installation outcome, commit boundaries, and recovery

Name the logical operation:

**`T_install(collection, version, destination)`**

During inspection, identify:

- its first destination mutation;
- staging and publication steps;
- associated metadata writes;
- its externally observed success indication.

This logical name does not itself imply a transaction.

### Existing durability, if present

Only if the implementation provides a real transactional publication path, name its actual commit barrier **`B_publish`** and record what makes it authoritative and durable.

The barrier must cover the claimed outcome, including relevant installation metadata. Atomic namespace replacement alone is not proof of power-loss durability.

For such a path, use the separate before-commit and after-commit tests in K10. A clock read or deadline expiry must never substitute for the commit barrier.

### Nontransactional behavior

If publication is incremental or lacks durable transaction semantics:

- Mark transactional rollback and durable-commit guarantees **unavailable**.
- Do not create a fictional commit barrier.
- Test first-mutation, partial-write, and completed-before-reply boundaries instead.
- Do not expand this PR into an atomic installer.

A command may leave earlier dependencies installed, and interruption may leave partial state. Neither an existing directory nor a missing reply proves success or rollback.

### Bounded recovery

After confirming writer exit, inspect:

- any authoritative receipt the implementation already provides;
- destination version/manifest;
- expected file inventory and hashes;
- installation side metadata;
- pointer or symlink state, if publication uses one.

Classify the outcome as **absent, complete, partial, or unavailable**. Unreadable or internally inconsistent state is not success.

Perform at most one recovery replay per fault scenario, within its test timeout. Preserve normal checks and ordinary no-force behavior. A completed same-version installation should use existing skip behavior rather than create another publication.

Do not add a receipt store or claim exactly-once crash recovery. If existing replay semantics cannot establish nonduplication, report that limitation rather than silently changing unrelated behavior.

## K08 — Workflow deadline, admission, and stopping

The workflow deadline is **50 minutes from a monotonic start time**. It is not a new CLI deadline or lease feature.

| Time | Activity |
|---|---|
| 0–6 min | Inspect call graph, classifications, tests, and publication behavior |
| 6–19 min | Implement the narrow change |
| 19–29 min | Add focused parser, propagation, proxy, and provider tests |
| 29–39 min | Run selected local integration and existing regression tests |
| 39–47 min | At most two targeted repair-and-retest cycles |
| 47–50 min | Stop remaining work, inspect outcomes, review diff, and close out |

Treat each repair plus its retest as one cycle. Do not begin a third.

Admit tests in priority order under the admission rule below:

1. A01–A08 and the existing CLI, proxy, and collection-install regression suites covering the PR contracts.
2. A09–A10 and B01–B05.
3. B06, B09, and the applicable B07/B08 tests or their nontransactional alternatives.

A lower-priority test that does not fit the remaining allocation is reported as not run. It is not started and then abandoned.

### Admission and expiry

Before admitting a command or repair, ensure its timeout, recovery allowance, and cleanup fit before the reserved closeout period and within the remaining cost cap.

Use available cost accounting; do not authorize work whose bounded cost would exceed $10. If remaining expenditure cannot be bounded, stop rather than assume it is affordable.

Expiry stops admission. It does **not** establish that an in-flight installation rolled back or cannot still publish.

An already admitted operation may finish before termination takes effect. Inspect authoritative state to determine its outcome. A clock read, timeout, or lease expiry alone is not a commit fence.

### Bounded waits

- Default focused test timeout: 120 seconds; permit up to 180 seconds only when it fits the remaining allocation.
- Bound injected barrier waits and recovery inspection by the enclosing test timeout.
- Reserve five seconds per active worker for termination and reaping.
- On timeout, terminate the owned process group, allow two seconds for graceful exit, then kill it if needed and allow three seconds to reap it.
- Track descendants, not only the immediate test process.
- Do not retry or remove a fixture until all owned writers are confirmed stopped.

If exit or state inspection cannot be confirmed within the bound, preserve the fixture and report **stop unconfirmed; outcome unavailable**.

### Stop acknowledgement

No durable stop-acknowledgement protocol is introduced.

A durable stop acknowledgement would require persistent terminal state and fencing that prevents later publication. Neither deadline expiry nor process exit alone supplies that guarantee.

Do not report “cancelled with no effect” based on timeout, a termination request, or a lost reply. There is no new cancellation acknowledgement to emit.

## K09 — Proposed focused acceptance tests

Use existing test conventions and dependencies. These tests are proposed, not executed.

| Test and requirement | Setup and injected condition | Assertions | Captured evidence |
|---|---|---|---|
| **A01 — Exact CLI contract** | Construct collection-install parser; parse with and without the flag. | `store_true` action, exact destination/default/constant/help string, literal boolean results; unrelated commands unchanged. | Parser-action fields and parsed values. |
| **A02 — Install propagation** | Replace successive boundaries with spies; exercise omitted, false, true, and final-positional arguments. Also invoke any role-install or implicit-install requirements path that K02 shows reaches collection installation without registering `--offline`. | CLI → install → dependency map → builder receives the selected value; new parameters are final and positional-capable. Paths without the option forward `False` and raise no missing-argument error. | Signatures and ordered call arguments, including the non-collection-parser path. |
| **A03 — Supporting calls** | Exercise builder/proxy defaults and both values; call download with omitted, false, and true values. | Builder forwards its value; proxy retains it; download always resolves with `offline=False`. | Constructor and resolver-call assertions. |
| **A04 — Read-only state** | Construct independent true/false proxies; attempt property assignment. | Boolean identity is correct; assignment fails; no cross-instance state. | Values and exception. |
| **A05 — Empty remote candidates** | Offline name requirements with default and explicit API sources; API iterable and connection properties fail if accessed. | Empty set; no API iteration, version call, token access, or connection. | Zero-call counters and result. |
| **A06 — Local concrete path** | Local file/directory fixtures with concrete-manager spies. | Local version and dependencies remain available; no remote call. | Manager calls and results. |
| **A07 — Forbidden methods** | Direct metadata/signature calls on offline proxies, including explicit-source and primed-cache cases. | `NotImplementedError` occurs before API work or source recording. | Exception and zero-call assertions. |
| **A08 — Online compatibility** | Default/false proxies with successful APIs, multiple-server errors/fallback, metadata, and signatures. | Prior calls, ordering, recording, warnings, results, and exceptions remain unchanged. | Ordered calls and existing regression results. |
| **A09 — Provider and policy** | Compatible installed dependency, local artifact, missing/incompatible dependency, and locally satisfiable/unsatisfiable signature policies. | Installed candidates survive empty remote results; local resolution works; failures remain local; no verification downgrade. | Candidate maps, diagnostics, verification calls, network counters. |
| **A10 — Validation and lifetime** | Malicious archive fixture, denied destination, missing source, and paused artifact consumer. | Existing rejection behavior remains; context cleanup follows last use; replay does not bypass checks. | Exceptions, context/barrier trace, inventories. |

Run the relevant existing CLI, collection-install, extraction, proxy/API, and dependency-resolution tests as budget permits. Missing dependencies or an unavailable test runner are reported, not repaired by downloading packages.

## K10 — Proposed integration, outage, recovery, and cleanup tests

Use tiny deterministic local tarballs, an isolated collections path and configuration, and cleared ambient proxy/credential settings.

For offline integration tests, install fail-fast sentinels in the process that actually runs the CLI flow, before API or artifact setup. Cover connection/DNS entry points, relevant HTTP paths, and network-capable Git execution. Parent-process mocks alone do not instrument an unrelated child.

Keep online comparisons deterministic through local fakes or mocked transports; do not contact external Galaxy servers. Use only synthetic tokens and credential-free fake server URLs. Redact tokens, authorization headers, and URL credentials from recorded API calls, traces, and diagnostics. Capture sanitized output, exit status, counters, barrier ordering, and destination state under `/app`.

### B01 — Reported installed-dependency case

- **Setup:** Install a dependency from a local tarball, then prepare a local root tarball requiring its installed version.
- **Fault:** Make every network entry point fail immediately.
- **Assertions:** Offline installation succeeds; dependency is satisfied from the configured collection path; expected versions and contents are present; zero network attempts.
- **Replay:** Repeat without `--force`; verify existing same-version handling and no second publication or extra installation record.
- **Evidence:** Output, status, counters, manifest versions, hashes, and publication/extraction counts.

### B02 — All artifacts supplied locally

- **Setup:** Empty collections path; supply root and dependency tarballs using an arrangement supported by the repository.
- **Interleaving:** Parameterize input order.
- **Assertions:** Dependency ordering resolves locally; both expected collections install; no remote metadata or signatures are fetched.
- **Evidence:** Candidate selection, installed versions/hashes, and zero-network counters.

### B03 — Missing dependency through outage and recovery

- **Setup:** Root tarball with a missing or incompatible dependency; a fake configured server starts unavailable.
- **Interleaving:** Pause resolution, make the fake server available, then resume.
- **Assertions:** Offline resolution still fails locally within its bound; no server call or fallback occurs; no root success message. Confirm the existing resolve-before-install ordering leaves the root uninstalled.
- **Recovery:** Supply a compatible dependency locally and retry once.
- **Evidence:** Failure and recovery output, availability/barrier trace, counters, and before/after inventories.

### B04 — Online outage and recovery

- **Setup:** Equivalent dependency graph without `--offline`, using deterministic remote-response fakes.
- **Fault:** Inject an unavailable server followed by recovery or an existing alternate-server path.
- **Assertions:** Calls, metadata/signature behavior, fallback, and terminal result match existing behavior. If no retry exists, the initial command fails as before and a subsequent ordinary invocation succeeds after recovery; do not add retries.
- **Evidence:** Ordered API calls, diagnostics, and installed versions.

### B05 — Source and verification boundaries

- **Setup:** Remote tarball URL, remote Git source, supported requirements-file remote source, and a signature policy requiring unavailable remote material.
- **Fault:** Invoke offline with connection and Git sentinels.
- **Assertions:** Each unsupported or unsatisfiable case fails before network work; no signature-policy downgrade. Default/false comparisons retain existing source dispatch.
- **Evidence:** Diagnostics, zero offline attempts, verification calls, and online dispatch traces.

### B06 — Local-reference outage and cleanup races

- **Setup:** Pause immediately before opening a tarball or reading required installed metadata.
- **Fault:** Remove the pathname or inject `PermissionError`.
- **Assertions:** Failure is local, with no fallback or false success; unrelated installed collections remain unchanged.
- **Recovery:** Restore the source and replay once with ordinary checks.
- **Evidence:** Barrier trace, error, inventory, and replay result.

Separately pause **after** opening an artifact and request cleanup:

- Defer harness cleanup until the consumer and owned worker finish.
- Assert artifact-manager exit does not precede its final consumer.
- Permit continued reading from a valid open descriptor after unlink where the platform allows it; do not misclassify that as a failure.
- Record context lifetime and cleanup ordering.

Also replay with a changed or denied source/destination to verify that recovery does not bypass normal authorization, integrity, fencing, or reference-lifetime checks.

### B07 — Immediately BEFORE durable commit: definite rollback

Apply this test only if K02 establishes an existing durable transaction and identifies its real `B_publish`.

- **Transaction:** `T_install(collection, version, destination)`.
- **Setup:** Known baseline destination, local artifact, and offline sentinels.
- **Barrier/fault:** Pause immediately **BEFORE `B_publish`**, inject a transactional abort, and wait for rollback completion. Do not merely kill a process and assume rollback.
- **Assertions:** The transaction definitely rolled back; authoritative receipt, if present, and destination version/pointer remain at baseline. No success or cancellation acknowledgement is emitted.
- **Recovery/replay:** Confirm no old writer can publish, inspect authoritative state, then replay the same operation once. Normal authorization, integrity, fencing, and lifetime checks still run; only one successful effect is produced.
- **Evidence:** Abort/rollback trace, receipt inspection, baseline/recovered pointer and version, contents, and publication counts.

If rollback completion cannot be established, the result is unavailable—not a passing rollback test.

### B08 — Immediately AFTER durable commit but BEFORE reply

Keep this test separate from B07.

- **Transaction:** The same `T_install` and actual `B_publish`.
- **Setup:** Known baseline and local artifact.
- **Barrier/fault:** Pause immediately **AFTER durable `B_publish` but BEFORE success output/reply**, then lose the reply or terminate the worker.
- **Assertions:** The outcome is committed although the caller is initially uncertain. After recovery, authoritative receipt, if present, and destination pointer/version plus contents show the committed installation. No rollback or effect-free cancellation is inferred from the missing reply.
- **Recovery/replay:** Confirm writer exit; replay the same operation without `--force`. Retain all checks and verify no duplicate publication, receipt, or installation effect.
- **Evidence:** Commit-barrier trace, missing reply, recovered authoritative state, and replay/publication counts.

This is not a power-loss test unless the existing durability protocol and fault model support that claim.

### Nontransactional alternatives to B07/B08

If no durable transaction exists, mark B07/B08 inapplicable and propose separate tests:

1. Fault before the first destination mutation: verify no destination effect.
2. Fault during extraction or metadata writing: inspect actual partial-state and cleanup behavior.
3. Lose output after complete installation: inspect complete state and ordinary no-force replay.

Record absent, partial, complete, or unavailable outcomes. Do not label these alternatives “transaction rolled back” or “durably committed.”

### B09 — Timeout, publication, and stale-writer race

- **Setup:** Pause an owned worker during extraction or at a verified publication boundary.
- **Interleavings:** Exercise stop winning before release and completion winning before termination takes effect; concurrently request fixture cleanup.
- **Assertions:** Timeout is not treated as a commit fence. No cleanup or replay occurs while the old writer can act. No false success or cancellation acknowledgement is generated. After confirmed exit, classify authoritative state.
- **Evidence:** Barrier and termination ordering, descendant/reaping checks, destination inventory, and absence of premature cleanup.
- **Unavailable branch:** If stopping cannot be confirmed within the termination allowance, retain the fixture and report stop/outcome unavailable.

## K11 — Bounded closeout and completion gates

Before ending the implementation workflow:

- Review exact parser attributes and help text.
- Check final positional parameters, all forwarding paths, and download’s explicit false behavior.
- Check the read-only property, empty remote candidates, and required offline exceptions.
- Review supported offline paths for pre-proxy network escapes.
- Confirm installed candidates and local verification are retained.
- Review online regressions and security/lifetime checks.
- Keep the diff limited to relevant implementation, tests, and repository-required documentation.
- Stop and inspect remaining workers before fixture cleanup.

The implementation handoff should state changes, tests actually run, tests not run, and unresolved limitations. It must distinguish observed results from proposed tests.

If the time, cost, dependency, recovery, or repair limit prevents completion, stop with the remaining gap identified. Do not claim offline correctness, durable rollback, exactly-once replay, or durable cancellation without the corresponding evidence.