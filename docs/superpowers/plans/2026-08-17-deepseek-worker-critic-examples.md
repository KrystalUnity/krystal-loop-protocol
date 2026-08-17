# DeepSeek Worker And Independent Critic Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish a runnable, sanitized DeepSeek Codex worker example and a tested, provider-neutral read-only critic harness.

**Architecture:** The worker example runs one Codex process from an isolated `CODEX_HOME` with a bounded assignment and no authority escalation. The critic accepts one explicit JSON review packet, calls one OpenAI-compatible `/chat/completions` endpoint, rejects same-family independence claims, and writes only redacted request metadata, sanitized final provider content, and a validated verdict.

**Tech Stack:** Bash, Codex CLI configuration, Python 3 standard library, `unittest`, local `ThreadingHTTPServer`, JSON Schema document.

## Global Constraints

- Follow `docs/superpowers/specs/2026-08-17-deepseek-worker-critic-examples-design.md` exactly.
- Do not add runtime dependencies, services, databases, queues, or vector stores.
- Do not make a paid provider call during implementation or tests.
- Do not include private paths, credentials, KU routing, mission data, or internal coordination infrastructure.
- The worker may not certify itself; the critic may not edit or repair.
- The controller and human retain integration and publication authority.

---

### Task 1: DeepSeek Codex Worker Example

**Files:**
- Create: `examples/deepseek-codex-worker/README.md`
- Create: `examples/deepseek-codex-worker/config.toml.example`
- Create: `examples/deepseek-codex-worker/instructions.md`
- Create: `examples/deepseek-codex-worker/run.sh`
- Create: `examples/deepseek-codex-worker/assignment.example.md`
- Create: `examples/deepseek-codex-worker/expected-handover.json`
- Create: `examples/openai-compatible-critic/tests/test_critic.py`

**Interfaces:**
- Consumes: `DEEPSEEK_API_KEY`, an explicit workspace directory, and an assignment file.
- Produces: one ephemeral or caller-selected isolated Codex home and one bounded `codex exec` run.

- [ ] **Step 1: Write the failing worker-asset tests**

Add `WorkerExampleTests` to `test_critic.py`. Assert that all six worker files
exist, `run.sh` passes `bash -n`, no worker asset contains a private absolute
filesystem path, the launcher does not read `.env`, and the configuration
contains the selected DeepSeek provider, workspace-write sandbox, no approval
escalation, and disabled sandbox network access.

The regression test `test_worker_launcher_is_portable_and_contained` must fail
if `run.sh` begins sourcing a repository `.env` or embeds a host-specific path.

- [ ] **Step 2: Run the worker tests to verify RED**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
```

Expected: FAIL because the worker example files do not exist.

- [ ] **Step 3: Add the minimal worker profile and launcher**

`config.toml.example` pins:

```toml
model_provider = "deepseek"
model = "deepseek-v4-flash"
approval_policy = "never"
sandbox_mode = "workspace-write"

[model_providers.deepseek]
name = "DeepSeek"
base_url = "https://api.deepseek.com"
env_key = "DEEPSEEK_API_KEY"
wire_api = "responses"

[sandbox_workspace_write]
network_access = false
```

`run.sh` accepts exactly `WORKSPACE ASSIGNMENT_FILE`, checks `codex`, the key, directory, and file, creates an isolated temporary `CODEX_HOME` unless `KLP_CODEX_HOME` is explicitly supplied, installs the public config and instructions, registers only the selected workspace as trusted, and runs:

```bash
codex exec --strict-config --ephemeral -C "$workspace" - < "$assignment_file"
```

It must not source `.env`, forward the full parent environment deliberately, run Git, or invoke another agent.

- [ ] **Step 4: Add the assignment, handover, and README examples**

The assignment names one outcome, allowed and protected paths, forbidden actions, deterministic checks, evidence, budget, and stop conditions. The handover JSON reports revision identity supplied by the controller, changed files, check observations, evidence references, limitations, and stop reason; it contains no acceptance verdict.

- [ ] **Step 5: Run the worker tests to verify GREEN**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
bash -n examples/deepseek-codex-worker/run.sh
```

Expected: worker tests PASS and shell syntax exits 0.

---

### Task 2: Sealed OpenAI-Compatible Critic Harness

**Files:**
- Create: `examples/openai-compatible-critic/critic.py`
- Create: `examples/openai-compatible-critic/README.md`
- Create: `examples/openai-compatible-critic/review-packet.example.json`
- Create: `examples/openai-compatible-critic/verdict.schema.json`
- Modify: `examples/openai-compatible-critic/tests/test_critic.py`

**Interfaces:**
- Consumes: packet and schema paths, a new or empty output directory, timeout, optional independence requirement, and four `CRITIC_*` environment variables.
- Produces: `request.redacted.json`, `provider-response.json`, and, only after validation, `verdict.json`.

- [ ] **Step 1: Add failing critic behavior tests**

Use a local `ThreadingHTTPServer` and subprocess calls to `critic.py`. Add tests for:

```text
valid packet and verdict -> three artifacts
same worker/critic family -> no HTTP request
missing packet field -> no HTTP request
packet larger than 256 KiB -> no HTTP request
HTTP 500 -> no verdict
non-JSON assistant content -> no verdict
schema-invalid verdict -> no verdict
PASS plus blocking finding -> no verdict
```

Assert the fake API key appears in the request Authorization header, because the provider requires it, but never appears in stdout, stderr, or any output artifact.

- [ ] **Step 2: Run the critic tests to verify RED**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
```

Expected: critic tests FAIL because `critic.py`, the packet, and schema are absent.

- [ ] **Step 3: Add packet and verdict contracts**

The packet requires:

```text
protocol, task_id, objective, commitments, worker_provider_family,
base_revision, result_revision, changed_files, artifact_diff, checks,
evidence, known_limitations, unresolved_findings
```

The verdict schema closes additional properties and requires:

```text
reviewed_revision, critic_provider_family, critic_model, verdict, summary,
findings, limitations
```

Each finding requires `finding_id`, `severity`, `blocking`, `commitment`,
`observed`, `expected`, `evidence_refs`, and `repair_acceptance`.

- [ ] **Step 4: Implement packet validation and independence gate**

Implement `HarnessError`, `load_json`, `validate_packet`, and
`normalize_family`. Reject missing or blank required values, empty commitments
or checks, oversized serialized input, nonpositive timeouts, and same-family
review when `--require-independent` is set. Perform all checks before opening a
network connection.

- [ ] **Step 5: Implement one bounded provider call**

Use `urllib.request` with one POST to:

```text
{CRITIC_BASE_URL without trailing slash}/chat/completions
```

Send the configured model, fixed read-only system instruction, sealed packet,
verdict schema, `stream:false`, and `response_format:{"type":"json_object"}`.
Do not retry. Convert HTTP and URL errors into redacted diagnostics.

- [ ] **Step 6: Implement verdict validation and artifacts**

Implement the JSON Schema subset used by `verdict.schema.json`: object, array,
string, boolean, required, properties, additionalProperties, enum, minItems,
and minLength. Verify `reviewed_revision`, critic family, and model against
controller-owned values. Reject `PASS` and `PASS_WITH_NONBLOCKING_FINDINGS`
when any finding is blocking.

Write JSON atomically. Strip provider reasoning fields by constructing
`provider-response.json` only from `id`, `model`, `usage`, and final assistant
content. Never serialize headers or the API key.

- [ ] **Step 7: Run the complete tests to verify GREEN**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
```

Expected: all worker and critic tests PASS with no external egress.

---

### Task 3: Public Documentation And Release Verification

**Files:**
- Modify: `README.md`
- Modify: `AI_AGENT_INTEGRATION.md`
- Modify: `docs/superpowers/specs/2026-08-17-deepseek-worker-critic-examples-design.md`

**Interfaces:**
- Consumes: the verified examples from Tasks 1 and 2.
- Produces: discoverable public instructions and an implementation-complete design status.

- [ ] **Step 1: Link the examples from the root README**

Add a short `Runnable Example` section explaining:

```text
DeepSeek Flash bounded worker
-> factual handover and deterministic checks
-> sealed review packet
-> different-family read-only critic
-> human decision
```

State that model price and capability do not change assignment or authority.

- [ ] **Step 2: Add the critic handoff to the agent integration guide**

Link the sealed packet and verdict contract from `AI_AGENT_INTEGRATION.md`.
State that DeepSeek Flash and DeepSeek Pro are the same provider family for
independence purposes.

- [ ] **Step 3: Mark the design implemented after evidence passes**

Change the design status only after the full local suite and public scans pass.

- [ ] **Step 4: Run complete verification**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
bash -n examples/deepseek-codex-worker/run.sh
python3 -m py_compile examples/openai-compatible-critic/critic.py
python3 -m json.tool examples/deepseek-codex-worker/expected-handover.json >/dev/null
python3 -m json.tool examples/openai-compatible-critic/review-packet.example.json >/dev/null
python3 -m json.tool examples/openai-compatible-critic/verdict.schema.json >/dev/null
git diff --check
```

Then run relative-link, non-ASCII, private-marker, common-secret, and forbidden
absolute-path scans over the public tree.

- [ ] **Step 5: Request one bounded independent review**

Review the exact candidate revision against the approved design. Accept only
material findings. Do not start an automatic repair loop or second critic.

- [ ] **Step 6: Commit and publish only after verification**

Stage the example, test, documentation, spec, and plan files explicitly. Commit
the verified implementation, push `main`, and compare the public remote SHA and
raw files to the local commit.
