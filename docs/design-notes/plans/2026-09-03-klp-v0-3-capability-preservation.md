# KLP v0.3 Capability Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade KLP from task-only conformance to mission-bound work that cannot complete when an affected critical product capability is degraded or unproven.

**Architecture:** Add a portable v0.3 Mission Contract and task-binding validator, then prove the lifecycle with a self-contained offline capability-regression fixture. Keep the existing v0.2 fixture operational for compatibility, extend the worker and critic examples to carry mission context, and update normative, runtime, safety, Hermes, and plain-language guidance around the tested record shapes.

**Tech Stack:** Markdown, JSON, Python 3 standard library, `unittest`, Git, and the existing loopback OpenAI-compatible critic harness.

**Spec:** `docs/superpowers/specs/2026-09-03-klp-v0-3-capability-preservation-design.md`

## Global Constraints

- Use protocol identity `klp-core/v0.3` for new records; preserve v0.2 fixture compatibility.
- Every v0.3 task must bind to one exact Mission Contract revision and digest.
- At least one critical capability is required in a Mission Contract.
- Critical capability dispositions `degraded` and `unproven` prevent completion.
- Mission amendments require both a technical explanation and a plain-English Operator Impact Statement.
- No test or fixture may use a paid provider, external network, live application, credential, production mutation, or consequential action.
- The Capability Auditor is mechanical and read-only; it cannot be the worker whose artifact it checks.
- Green task checks and critic verdicts cannot override a failed or inconclusive capability probe.
- Existing v0.2 records remain v0.2 records and must not be silently promoted to v0.3.
- Keep runtime dependencies at Python standard library only.
- Each commit stages only the files named by its task.

---

### Task 1: Mission Contract Records And Validation

**Files:**
- Create: `examples/capability-regression/klp_v03.py`
- Create: `examples/capability-regression/example_records.py`
- Create: `examples/capability-regression/records/mission-contract.example.json`
- Create: `examples/capability-regression/records/task-contract.example.json`
- Create: `examples/capability-regression/records/mission-amendment.example.json`
- Create: `examples/capability-regression/tests/test_contracts.py`

**Interfaces:**
- Produces: `ContractError(ValueError)` for invalid protocol records.
- Produces: `canonical_json(value: object) -> bytes` and `digest(value: object) -> str`, where the digest is prefixed with `sha256:`.
- Produces: `validate_mission_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]`, returning the validated mission body.
- Produces: `validate_task_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]` and `matching_capability_ids(mission: dict[str, Any], changed_surfaces: list[str]) -> set[str]`.
- Produces: `validate_task_binding(mission_snapshot: dict[str, Any], task_snapshot: dict[str, Any], changed_surfaces: list[str]) -> set[str]`, returning triggered capability IDs or raising `ContractError`.
- Produces: `validate_amendment_request(request: dict[str, Any]) -> None`.
- Produces: `build_authorized_mission_revision(current_snapshot: dict[str, Any], request: dict[str, Any], amended_mission: dict[str, Any], operator_authority_ref: str) -> dict[str, Any]`.
- Produces: `build_example_records() -> dict[str, dict[str, Any]]` and a CLI that rewrites the three committed JSON examples deterministically.
- Consumes later: Tasks 2 and 3 import all validation functions and record builders directly from this directory.

- [ ] **Step 1: Write failing contract tests**

Create `tests/test_contracts.py` with path-local imports and these cases:

```python
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


FIXTURE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(FIXTURE_DIR))

from example_records import build_example_records  # noqa: E402
from klp_v03 import (  # noqa: E402
    ContractError,
    digest,
    validate_amendment_request,
    build_authorized_mission_revision,
    validate_mission_snapshot,
    validate_task_binding,
)


class ContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.records = build_example_records()
        self.mission = self.records["mission-contract.example.json"]
        self.task = self.records["task-contract.example.json"]

    def test_example_records_are_valid_and_digest_bound(self) -> None:
        body = validate_mission_snapshot(self.mission)
        self.assertEqual(digest(body), self.mission["identity"]["mission_hash"])
        triggered = validate_task_binding(
            self.mission, self.task, ["path:chooser.py"]
        )
        self.assertEqual({"adaptive-choice"}, triggered)
        validate_amendment_request(
            self.records["mission-amendment.example.json"]
        )

    def test_stale_mission_hash_is_rejected(self) -> None:
        task = copy.deepcopy(self.task)
        task["task"]["mission_hash"] = "sha256:stale"
        with self.assertRaisesRegex(ContractError, "mission hash"):
            validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_triggered_but_undeclared_capability_is_rejected(self) -> None:
        task = copy.deepcopy(self.task)
        task["task"]["affected_capabilities"] = []
        with self.assertRaisesRegex(ContractError, "adaptive-choice"):
            validate_task_binding(self.mission, task, ["path:chooser.py"])

    def test_amendment_requires_both_explanations(self) -> None:
        request = copy.deepcopy(
            self.records["mission-amendment.example.json"]
        )
        request.pop("operator_impact_statement")
        with self.assertRaisesRegex(ContractError, "plain-English"):
            validate_amendment_request(request)

    def test_committed_examples_match_the_generator(self) -> None:
        records_dir = FIXTURE_DIR / "records"
        for name, expected in self.records.items():
            actual = json.loads((records_dir / name).read_text(encoding="utf-8"))
            self.assertEqual(expected, actual)

    def test_authorized_revision_preserves_parent_and_authority(self) -> None:
        body = copy.deepcopy(self.mission["mission"])
        body["critical_capabilities"][0]["required_behavior"] = (
            "Return one fixed safe action for every signal."
        )
        revised = build_authorized_mission_revision(
            self.mission,
            self.records["mission-amendment.example.json"],
            body,
            "operator-decision:fixture-001",
        )
        self.assertEqual(2, revised["identity"]["mission_revision"])
        self.assertEqual(
            self.mission["identity"]["mission_hash"],
            revised["identity"]["parent_mission_hash"],
        )
        self.assertEqual(
            "operator-decision:fixture-001",
            revised["identity"]["authority_ref"],
        )
```

- [ ] **Step 2: Run the tests and confirm the missing-module failure**

Run:

```bash
python3 examples/capability-regression/tests/test_contracts.py -v
```

Expected: FAIL because `example_records` and `klp_v03` do not exist.

- [ ] **Step 3: Implement strict record validation**

Create `klp_v03.py` with standard-library-only helpers. Validate required
strings, positive revisions, arrays, identity/body digest agreement, unique
capability IDs, severity `critical`, supported expected deltas, and every
required amendment field.

The trigger evaluator must use `fnmatch.fnmatchcase` over typed surface strings
such as `path:chooser.py`, `interface:choose_action`, `prompt:system`, and
`config:model`. Its core behavior is:

```python
def validate_task_binding(
    mission_snapshot: dict[str, Any],
    task_snapshot: dict[str, Any],
    changed_surfaces: list[str],
) -> set[str]:
    mission = validate_mission_snapshot(mission_snapshot)
    task = validate_task_snapshot(task_snapshot)
    identity = mission_snapshot["identity"]
    if task["mission_id"] != identity["mission_id"]:
        raise ContractError("task mission id does not match Mission Contract")
    if task["mission_revision"] != identity["mission_revision"]:
        raise ContractError("task mission revision does not match Mission Contract")
    if task["mission_hash"] != identity["mission_hash"]:
        raise ContractError("task mission hash does not match Mission Contract")

    triggered = matching_capability_ids(mission, changed_surfaces)
    declared = set(task["affected_capabilities"])
    omitted = triggered - declared
    if omitted:
        raise ContractError(
            "triggered capability not declared: " + ", ".join(sorted(omitted))
        )
    return triggered
```

`validate_amendment_request` must require nonempty values for:

```text
technical_explanation.fields_changed[]
technical_explanation.evidence_refs[]
technical_explanation.behavioral_impact
technical_explanation.architectural_impact
technical_explanation.testing_impact
technical_explanation.safety_impact
technical_explanation.compatibility_impact
technical_explanation.alternatives_considered[]
technical_explanation.rollback_implications
technical_explanation.duration
operator_impact_statement.today
operator_impact_statement.after
operator_impact_statement.user_may_lose
operator_impact_statement.expected_benefit
operator_impact_statement.if_declined
```

`build_authorized_mission_revision` does not decide whether an amendment is
authorized. It requires a nonempty operator authority reference supplied by
the caller, validates the request and current snapshot, sets revision to the
current revision plus one, binds `parent_mission_hash` to the current digest,
and computes a new digest over the supplied amended body. Reject an empty
authority reference and any request targeting a different mission ID or hash.

- [ ] **Step 4: Build deterministic example records**

Create `example_records.py`. The Mission Contract must define one critical
capability, `adaptive-choice`, with these trigger rules:

```python
["path:chooser.py", "interface:choose_action", "config:decision-policy"]
```

Its positive controls require `fire -> evacuate` and `medical -> assist`. Its
negative controls require `unknown -> observe`, reject constant output, and
require `decision_source == "input-dependent"`.

The Task Contract must declare `adaptive-choice`, expected delta `preserve`,
the exact Mission Contract hash, allowed path `chooser.py`, and required probe
`adaptive-choice-product-truth`.

The amendment example must include all technical fields and this complete
plain-English shape:

```python
{
    "today": "Today the product selects different actions from the supplied signal.",
    "after": "After this amendment, it may return one fixed safe action.",
    "user_may_lose": "Users may lose adaptive decisions for supported signals.",
    "expected_benefit": "The fixed action would reduce decision variability.",
    "if_declined": "The current adaptive capability and its existing limits remain.",
}
```

Compute `mission_hash` from the mission body and `contract_hash` from the task
body. The CLI writes sorted, indented JSON with a trailing newline using an
atomic temporary-file replacement.

- [ ] **Step 5: Generate the committed examples and run the contract tests**

Run:

```bash
python3 examples/capability-regression/example_records.py
python3 examples/capability-regression/tests/test_contracts.py -v
```

Expected: all six tests PASS and rerunning the generator leaves the files
byte-identical.

- [ ] **Step 6: Commit Task 1**

```bash
git add examples/capability-regression/klp_v03.py examples/capability-regression/example_records.py examples/capability-regression/records examples/capability-regression/tests/test_contracts.py
git commit -m "feat: add KLP v0.3 mission contracts"
```

---

### Task 2: Offline Capability Regression And Repair Fixture

**Files:**
- Create: `examples/capability-regression/run_fixture.py`
- Create: `examples/capability-regression/tests/test_fixture.py`

**Interfaces:**
- Consumes: `digest`, `validate_mission_snapshot`, and `validate_task_binding` from `klp_v03.py`.
- Consumes: canonical records from `build_example_records()`.
- Produces CLI: `run_fixture.py --out-dir PATH [--repair-round-limit N] [--probe-mode normal|inconclusive] [--omit-capability-declaration]`.
- Produces exit `0` for completed repair, `3` for exhausted repair budget, `4` for `capability_unproven`, `5` for `mission_mismatch`, and `2` for fixture setup errors.
- Produces: `mission.snapshot.json`, `task.snapshot.json`, `state-events.jsonl`, capability evidence, critic artifacts, and `final-receipt.json`.

- [ ] **Step 1: Write the failing completed-lifecycle test**

Create `tests/test_fixture.py` with these concrete helpers and the primary
assertion below:

```python
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "examples" / "capability-regression" / "run_fixture.py"


class CapabilityRegressionFixtureTests(unittest.TestCase):
    def run_fixture(
        self, output: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(FIXTURE), "--out-dir", str(output), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env={"PATH": os.environ.get("PATH", ""), "LANG": "C.UTF-8"},
        )

    def read_json(self, path: Path) -> dict[str, object]:
        value = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsInstance(value, dict)
        return value

    def read_states(self, path: Path) -> list[str]:
        return [
            json.loads(line)["new_state"]
            for line in path.read_text(encoding="utf-8").splitlines()
        ]

    def test_green_task_checks_cannot_hide_capability_regression(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture-output"
            result = self.run_fixture(output)

            self.assertEqual(0, result.returncode, result.stderr)
            states = self.read_states(output / "state-events.jsonl")
            self.assertIn("capability_regression", states)
            self.assertLess(
                states.index("capability_regression"), states.index("completed")
            )

            worker_check = (output / "evidence" / "worker-check.txt").read_text()
            failed_capability = self.read_json(
                output / "evidence" / "capability-after-integration-1.json"
            )
            repaired_capability = self.read_json(
                output / "evidence" / "capability-after-integration-2.json"
            )
            self.assertIn("OK", worker_check)
            restriction = self.read_json(
                output / "evidence" / "restriction-candidate.json"
            )
            self.assertEqual(
                "replace-adaptive-with-fixed-sequence",
                restriction["change_kind"],
            )
            self.assertEqual(
                ["adaptive-choice"], restriction["affected_capabilities"]
            )
            disposition = self.read_json(
                output / "evidence" / "restriction-disposition-2.json"
            )
            self.assertEqual("cleared", disposition["status"])
            self.assertIn(
                "evidence/capability-after-integration-2.json",
                disposition["evidence_refs"],
            )
            binding = self.read_json(output / "mission-binding-report.json")
            self.assertEqual("mission-custodian", binding["actor"])
            self.assertNotEqual(
                binding["actor"], binding["execution_coordinator"]
            )
            self.assertEqual("failed", failed_capability["result"])
            self.assertEqual(
                "capability-auditor", failed_capability["auditor_identity"]
            )
            self.assertEqual("passed", repaired_capability["result"])

            receipt = self.read_json(output / "final-receipt.json")
            self.assertEqual("klp-core/v0.3", receipt["protocol"])
            self.assertEqual("completed", receipt["status"])
            self.assertEqual(
                "preserved",
                receipt["capability_report"]["adaptive-choice"]["disposition"],
            )
            self.assertEqual(
                1, receipt["measured_budget"]["repair_rounds_used"]
            )
```

- [ ] **Step 2: Run the focused test and confirm the missing-fixture failure**

Run:

```bash
python3 examples/capability-regression/tests/test_fixture.py -v
```

Expected: FAIL because `run_fixture.py` does not exist.

- [ ] **Step 3: Implement the temporary adaptive-choice project**

`setup_workspace()` must create a temporary Git repository with:

```python
# chooser.py at the accepted baseline
def choose_action(signal: str) -> dict[str, str]:
    actions = {"fire": "evacuate", "medical": "assist"}
    return {
        "action": actions.get(signal, "observe"),
        "decision_source": "input-dependent",
    }
```

The protected task-level unit test checks only response shape and allowed action
vocabulary. The protected product-truth probe checks both positive controls,
the unknown-signal negative control, non-constant output, and decision
provenance.

The scripted worker revision replaces the adaptive implementation with:

```python
def choose_action(signal: str) -> dict[str, str]:
    return {"action": "observe", "decision_source": "fixed-policy"}
```

This worker revision must pass the declared task unit test.

Before accepting the worker unit, write `evidence/restriction-candidate.json`
with `change_kind: replace-adaptive-with-fixed-sequence`, affected capability
`adaptive-choice`, the worker revision, direct diff evidence, and status
`requires-preservation-proof`. This is the early tripwire; it does not replace
the later capability probe. It remains open while the bounded integration
candidate is created for testing. Do not mutate this record. Write
`restriction-disposition-1.json` as blocking after the failed result and
`restriction-disposition-2.json` as cleared only after a passing integrated
capability result.

- [ ] **Step 4: Implement lifecycle evidence and the mechanical auditor**

Implement these fixture utilities locally in `run_fixture.py` with exact
signatures: `write_json(path: Path, value: object) -> None`,
`prepare_output(path: Path) -> None`, `run_command(command: list[str], *, cwd:
Path, check: bool = True) -> subprocess.CompletedProcess[str]`,
`git(workspace: Path, *arguments: str) -> str`, and
`commit(workspace: Path, message: str) -> str`. Implement
`StateLedger.append(new_state: str, *, actor: str, reason: str,
artifact_revision: str | None) -> None`.

`write_json` uses a sibling `.tmp` file and atomic replacement.
`prepare_output` rejects an existing nonempty directory. `run_command` passes
only `PATH` and `LANG` to subprocesses, captures output, and raises
`FixtureError` when `check=True` and the command fails. `StateLedger` hashes
canonical JSON for every append-only event and includes `mission_revision`,
`mission_hash`, `contract_revision`, and `artifact_revision`.

After binding validation, write `mission-binding-report.json` with the Mission
Contract identity, Task Contract identity, changed surfaces, triggered and
declared capabilities, actor `mission-custodian`, execution coordinator
`execution-coordinator`, and result `passed`. Before a repair, write
`evidence/repair-mission-check.json`; before completion, write
`evidence/final-mission-check.json`. Both records must bind the current artifact
revision and state that no mission amendment was required.

Implement:

```python
def run_capability_probe(
    workspace: Path,
    evidence_path: Path,
    *,
    mission_hash: str,
    artifact_revision: str,
    baseline_revision: str,
    force_inconclusive: bool = False,
) -> dict[str, object]:
    if force_inconclusive:
        result = "inconclusive"
        observations: dict[str, object] = {
            "reason": "fixture-forced-inconclusive"
        }
    else:
        completed = run_command(
            [sys.executable, "capability_probe.py"],
            cwd=workspace,
            check=False,
        )
        try:
            observations = json.loads(completed.stdout)
        except json.JSONDecodeError:
            observations = {
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            result = "inconclusive"
        else:
            result = "passed" if completed.returncode == 0 else "failed"

    record = {
        "capability_id": "adaptive-choice",
        "mission_hash": mission_hash,
        "artifact_revision": artifact_revision,
        "baseline_revision": baseline_revision,
        "positive_control": ["fire -> evacuate", "medical -> assist"],
        "negative_control": [
            "unknown -> observe",
            "outputs are not constant",
        ],
        "expected_observations": {
            "decision_source": "input-dependent",
        },
        "actual_observations": observations,
        "decision_provenance": observations.get("decision_sources", []),
        "auditor_identity": "capability-auditor",
        "limits": {"external_cost_usd": 0, "attempts": 1},
        "result": result,
        "evidence_refs": [str(evidence_path.relative_to(evidence_path.parents[1]))],
    }
    write_json(evidence_path, record)
    return record
```

It runs the protected probe script with `subprocess.run`, captures direct
stdout/stderr, and emits the exact record fields from the design. It returns
`result: passed|failed|inconclusive`; it never edits the workspace.

- [ ] **Step 5: Reuse the sealed critic harness for task-level PASS evidence**

Implement `FakeCriticProvider`, `provider_verdict`, and `run_critic` inside the
fixture. `FakeCriticProvider` binds only to `127.0.0.1` on an ephemeral port,
counts requests, returns one scripted Chat Completions JSON response, and
shuts down its thread on context exit. `run_critic` invokes
`examples/openai-compatible-critic/critic.py` with a two-second timeout and
fails unless exactly one loopback request occurred. The review packet must use
`klp-core/v0.3`, include the exact Mission Contract identity,
`affected_capabilities`, `capability_commitments`,
`expected_capability_delta`, `required_capability_probes`, and
`baseline_evidence_refs`, and remain tied to the exact worker revision. Each
capability commitment is copied from the digest-bound Mission Contract and
contains its ID, required behavior, forbidden regressions, and decision
provenance requirement.

The scripted critic passes the worker's narrow task commitments. The fixture
must then integrate that accepted unit and prove that the separate capability
gate fails. This ordering is the central regression proof.

- [ ] **Step 6: Implement one bounded repair and second integration**

After `capability_regression`, restore the input-dependent implementation,
rerun the task check, obtain a fresh task critic PASS, create a new integration
revision, and rerun the capability probe. Append `final_review` and `completed`
only after the second capability result passes and
`restriction-disposition-2.json` binds that passing evidence to the original
restriction candidate.

The Final Receipt must include:

```python
{
    "protocol": "klp-core/v0.3",
    "mission_identity": mission_snapshot["identity"],
    "contract_identity": task_snapshot["identity"],
    "status": "completed",
    "capability_report": {
        "adaptive-choice": {
            "before": "passed",
            "after": "passed",
            "intermediate": "failed",
            "disposition": "preserved",
            "evidence_refs": [
                "evidence/capability-baseline.json",
                "evidence/capability-after-integration-1.json",
                "evidence/capability-after-integration-2.json",
            ],
        }
    },
    "limitations": [
        "The worker and critic are scripted.",
        "The fixture proves protocol gating, not model quality or production safety.",
    ],
}
```

- [ ] **Step 7: Run the completed-lifecycle test**

Run:

```bash
python3 examples/capability-regression/tests/test_fixture.py -v
```

Expected: the primary lifecycle test PASS.

- [ ] **Step 8: Commit Task 2**

```bash
git add examples/capability-regression/run_fixture.py examples/capability-regression/tests/test_fixture.py
git commit -m "feat: prove capability regression gating"
```

---

### Task 3: Mission And Capability Stop Paths

**Files:**
- Modify: `examples/capability-regression/run_fixture.py`
- Modify: `examples/capability-regression/tests/test_contracts.py`
- Modify: `examples/capability-regression/tests/test_fixture.py`

**Interfaces:**
- Extends: Task 2 CLI exit codes and Final Receipt status handling.
- Consumes: `validate_amendment_request` and `validate_task_binding` from Task 1.
- Produces: bounded terminal receipts for `budget_exhausted`, `capability_unproven`, and `mission_mismatch`.

- [ ] **Step 1: Add failing stop-path tests**

Add `from contextlib import contextmanager` with the module imports, then add
these methods inside `CapabilityRegressionFixtureTests`:

```python
    @contextmanager
    def fixture_output(self, *arguments: str):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "fixture-output"
            yield self.run_fixture(output, *arguments), output

    def test_zero_repair_budget_stops_after_capability_regression(self) -> None:
        with self.fixture_output("--repair-round-limit", "0") as (result, output):
            self.assertEqual(3, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assertEqual("budget_exhausted", receipt["status"])
            self.assertEqual(
                "degraded",
                receipt["capability_report"]["adaptive-choice"]["disposition"],
            )
            self.assertFalse(
                (
                    output
                    / "evidence"
                    / "capability-after-integration-2.json"
                ).exists()
            )

    def test_inconclusive_probe_cannot_complete(self) -> None:
        with self.fixture_output("--probe-mode", "inconclusive") as (result, output):
            self.assertEqual(4, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assertEqual("capability_unproven", receipt["status"])
            self.assertNotIn(
                "completed", self.read_states(output / "state-events.jsonl")
            )

    def test_undeclared_trigger_stops_before_worker_execution(self) -> None:
        with self.fixture_output("--omit-capability-declaration") as (result, output):
            self.assertEqual(5, result.returncode, result.stderr)
            receipt = self.read_json(output / "final-receipt.json")
            self.assertEqual("mission_mismatch", receipt["status"])
            self.assertFalse((output / "evidence" / "worker-check.txt").exists())
```

Extend amendment tests to remove `technical_explanation`, then make
`operator_impact_statement.after` empty. Both must raise `ContractError`; a
complete request must pass.

- [ ] **Step 2: Run tests and confirm all new cases fail**

Run:

```bash
python3 examples/capability-regression/tests/test_contracts.py -v
python3 examples/capability-regression/tests/test_fixture.py -v
```

Expected: existing tests PASS and the new stop-path tests FAIL.

- [ ] **Step 3: Implement stop receipts without fall-through**

Add one helper:

```python
def write_terminal_receipt(
    output: Path,
    *,
    status: str,
    mission_identity: dict[str, object],
    contract_identity: dict[str, object],
    capability_report: dict[str, object],
    ledger: StateLedger,
    human_decisions_required: list[str],
) -> None:
    evidence_refs = sorted(
        {
            reference
            for value in capability_report.values()
            if isinstance(value, dict)
            for reference in value.get("evidence_refs", [])
            if isinstance(reference, str)
        }
    )
    write_json(
        output / "final-receipt.json",
        {
            "protocol": "klp-core/v0.3",
            "status": status,
            "mission_identity": mission_identity,
            "contract_identity": contract_identity,
            "capability_report": capability_report,
            "claims": [
                "The run stopped without claiming mission-preserving completion."
            ],
            "evidence_refs": evidence_refs,
            "limitations": [
                "This is an offline synthetic protocol fixture."
            ],
            "unresolved_findings": [],
            "human_decisions_required": human_decisions_required,
            "state_ledger_tail_hash": ledger.tail_hash,
        },
    )
```

Each stop branch must append exactly one terminal state, write the receipt, and
return immediately. `--omit-capability-declaration` mutates only the fixture's
in-memory Task Contract before validation; it must never rewrite a committed
example record.

For `--probe-mode inconclusive`, the baseline remains valid and the first
post-integration probe becomes inconclusive. Do not enter repair because there
is no measured defect to repair.

- [ ] **Step 4: Run all capability fixture tests**

Run:

```bash
python3 examples/capability-regression/tests/test_contracts.py -v
python3 examples/capability-regression/tests/test_fixture.py -v
```

Expected: all tests PASS; no test performs non-loopback network access.

- [ ] **Step 5: Commit Task 3**

```bash
git add examples/capability-regression/run_fixture.py examples/capability-regression/tests/test_contracts.py examples/capability-regression/tests/test_fixture.py
git commit -m "test: enforce KLP mission stop states"
```

---

### Task 4: v0.3 Worker And Critic Compatibility

**Files:**
- Modify: `examples/openai-compatible-critic/critic.py`
- Modify: `examples/openai-compatible-critic/tests/test_critic.py`
- Modify: `examples/openai-compatible-critic/review-packet.example.json`
- Modify: `examples/openai-compatible-critic/README.md`
- Modify: `examples/deepseek-codex-worker/assignment.example.md`
- Modify: `examples/deepseek-codex-worker/expected-handover.json`
- Modify: `examples/deepseek-codex-worker/instructions.md`
- Modify: `examples/deepseek-codex-worker/README.md`

**Interfaces:**
- Preserves: current v0.2 critic packets and all existing tests.
- Adds: v0.3 packet fields `mission_id`, `mission_revision`, `mission_hash`, `affected_capabilities`, `capability_commitments`, `expected_capability_delta`, `required_capability_probes`, and `baseline_evidence_refs`.
- Adds: `system_prompt_for(packet: dict[str, Any], independent: bool) -> str`.
- Adds worker handover facts: `mission_hash`, `affected_capabilities`, and `capability_risks_observed`; workers still cannot certify preservation.

- [ ] **Step 1: Add failing v0.3 critic tests**

Add `valid_v03_packet()` by copying `valid_packet()`, setting the protocol to
`klp-core/v0.3`, and adding all eight mission fields. Add tests that prove:

```python
def test_v03_packet_requires_mission_binding_before_http(self) -> None:
    packet = valid_v03_packet()
    packet.pop("mission_hash")
    with FakeProvider(self.provider_payload(valid_verdict())) as provider:
        result, artifacts = self.run_harness(packet, provider)
    self.assertNotEqual(0, result.returncode)
    self.assertIn("mission_hash", result.stderr)
    self.assertEqual(0, provider.request_count)
    self.assertNotIn("verdict.json", artifacts)

def test_v03_critic_is_told_it_cannot_certify_capability(self) -> None:
    with FakeProvider(self.provider_payload(valid_verdict())) as provider:
        result, _ = self.run_harness(valid_v03_packet(), provider)
    self.assertEqual(0, result.returncode, result.stderr)
    system = provider.request_body["messages"][0]["content"]
    self.assertIn("Mission Contract", system)
    self.assertIn("cannot satisfy the capability gate", system)

def test_v03_packet_requires_relevant_capability_commitment(self) -> None:
    packet = valid_v03_packet()
    packet["capability_commitments"] = []
    with FakeProvider(self.provider_payload(valid_verdict())) as provider:
        result, artifacts = self.run_harness(packet, provider)
    self.assertNotEqual(0, result.returncode)
    self.assertIn("capability_commitments", result.stderr)
    self.assertEqual(0, provider.request_count)
    self.assertNotIn("verdict.json", artifacts)
```

Keep one explicit test proving an unchanged v0.2 packet still succeeds.

- [ ] **Step 2: Run critic tests and confirm the new tests fail**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
```

Expected: existing tests PASS; new v0.3 tests FAIL.

- [ ] **Step 3: Implement protocol-sensitive packet validation**

Replace one global required tuple with:

```python
SUPPORTED_PROTOCOLS = {"klp-core/v0.2", "klp-core/v0.3"}
PACKET_REQUIRED_COMMON = (
    "protocol",
    "task_id",
    "contract_id",
    "contract_revision",
    "contract_hash",
    "objective",
    "commitments",
    "worker_provider_family",
    "base_revision",
    "result_revision",
    "changed_files",
    "artifact_diff",
    "checks",
    "evidence",
    "known_limitations",
    "unresolved_findings",
)
PACKET_REQUIRED_V03 = (
    "mission_id",
    "mission_revision",
    "mission_hash",
    "affected_capabilities",
    "capability_commitments",
    "expected_capability_delta",
    "required_capability_probes",
    "baseline_evidence_refs",
)
```

Reject unknown protocol versions. For v0.3, require nonempty mission ID/hash,
a positive mission revision, `preserve|improve` as the expected delta, and
arrays for the four capability collection fields.
`affected_capabilities` may be empty because a verified no-impact task is
valid. When it is nonempty, `capability_commitments` and
`required_capability_probes` must also be nonempty.

Build the system prompt per packet. For v0.3 append:

```text
The task is bound to a Mission Contract. Review declared capability impact and
flag evidence of an omitted impact or capability restriction as a finding.
Your verdict evaluates the sealed task artifact only and cannot satisfy or
override the separate mechanical capability gate.
```

- [ ] **Step 4: Update machine-readable worker and critic examples**

Convert `review-packet.example.json` to v0.3 and add the eight required fields.
Add the matching Mission Contract hash and affected capability to the worker
assignment. Add these facts to `expected-handover.json`:

```json
"mission_hash": "sha256:mission-example-123",
"affected_capabilities": ["title-normalization"],
"capability_risks_observed": []
```

State explicitly in both READMEs and `instructions.md` that the worker reports
observed risk but neither worker nor critic can pass the capability gate.

- [ ] **Step 5: Run critic and worker-example tests**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
bash -n examples/deepseek-codex-worker/run.sh
```

Expected: all tests PASS and the shell launcher remains syntactically valid.

- [ ] **Step 6: Commit Task 4**

```bash
git add examples/openai-compatible-critic examples/deepseek-codex-worker
git commit -m "feat: carry mission context through agent examples"
```

---

### Task 5: Normative v0.3 Protocol And Agent Records

**Files:**
- Modify: `PROTOCOL.md`
- Modify: `AI_AGENT_INTEGRATION.md`
- Create: `tests/test_v03_documentation.py`

**Interfaces:**
- Consumes: exact record fields and lifecycle states implemented by Tasks 1-3.
- Produces: normative `klp-core/v0.3` rules and minimum integration record shape.
- Produces: static conformance checks reused by Task 6.

- [ ] **Step 1: Write failing normative-document tests**

Create `tests/test_v03_documentation.py`:

```python
from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class V03DocumentationTests(unittest.TestCase):
    def text(self, relative: str) -> str:
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_normative_protocol_contains_capability_gate(self) -> None:
        protocol = self.text("PROTOCOL.md")
        for required in (
            "Version: 0.3 draft",
            "## Mission Contract",
            "mission_binding_check",
            "capability_baseline",
            "capability_check",
            "mission_mismatch",
            "capability_regression",
            "capability_unproven",
            "mission_amendment_requested",
            "plain-English Operator Impact Statement",
        ):
            self.assertIn(required, protocol)

    def test_agent_guide_requires_mission_recovery_fields(self) -> None:
        guide = self.text("AI_AGENT_INTEGRATION.md")
        for required in (
            "mission_id",
            "mission_revision",
            "mission_hash",
            "affected_capabilities[]",
            "capability_commitments[]",
            "expected_capability_delta",
            "required_capability_probes[]",
            "capability_report",
        ):
            self.assertIn(required, guide)
```

- [ ] **Step 2: Run the normative tests and confirm failure against v0.2 docs**

Run:

```bash
python3 tests/test_v03_documentation.py -v
```

Expected: FAIL because the current normative files describe v0.2 only.

- [ ] **Step 3: Upgrade `PROTOCOL.md` to the approved authority hierarchy**

Change the status to `Version: 0.3 draft`. Add the Mission Contract as the
persistent authority above disposable Task Contracts. Add Mission Custodian
and Capability Auditor roles, the approved lifecycle ordering, all four new
stop states, and the five new records from the design.

Add hard rules that state exactly:

- a v0.3 task cannot be approved without exact Mission Contract binding;
- trigger matches must be declared and verified;
- a critical capability requires accepted baseline and integrated-artifact
  evidence;
- `degraded` or `unproven` blocks completion;
- task checks and critic verdicts cannot override capability results;
- capability restrictions require direct preservation evidence;
- mission amendments require technical and plain-English explanations;
- only the operator may authorize a Mission Contract revision.

Keep the existing finding adjudication, budgets, artifact identity, and live
authority rules. Update Completion so a v0.3 Final Receipt is incomplete
without mission identity and capability dispositions.

- [ ] **Step 4: Upgrade `AI_AGENT_INTEGRATION.md` record flow**

Update bootstrap instructions so every role reads the exact Mission Contract
from authoritative storage rather than memory. Add the new minimum fields,
capability report shape, amendment request shape, and v0.3 message-envelope
fields.

Worker handovers report facts and `capability_risks_observed[]`; they cannot
claim preservation. Task critics assess declared impact but cannot satisfy the
mechanical gate. The Mission Custodian checks alignment at approval, repair,
integration, and final review.

Add stop behavior for missing/stale mission identity, undeclared triggers,
failed probes, inconclusive probes, and amendment requests.

- [ ] **Step 5: Run normative and existing harness tests**

Run:

```bash
python3 tests/test_v03_documentation.py -v
python3 examples/openai-compatible-critic/tests/test_critic.py -v
python3 examples/fail-review-repair/tests/test_fixture.py -v
```

Expected: all tests PASS; the v0.2 lifecycle proof remains unchanged.

- [ ] **Step 6: Commit Task 5**

```bash
git add PROTOCOL.md AI_AGENT_INTEGRATION.md tests/test_v03_documentation.py
git commit -m "docs: define KLP v0.3 capability gate"
```

---

### Task 6: Runtime, Safety, Hermes, And Plain-Language Guidance

**Files:**
- Modify: `RUNTIME_PROFILES.md`
- Modify: `SAFETY_AND_LIMITS.md`
- Modify: `adapters/hermes-kanban.md`
- Modify: `README.md`
- Create: `examples/capability-regression/README.md`
- Modify: `tests/test_v03_documentation.py`

**Interfaces:**
- Consumes: v0.3 records, states, fixture CLI, and role boundaries from Tasks 1-5.
- Produces: portable deployment profiles, Hermes mapping, public quick-start prompt, and fixture instructions.

- [ ] **Step 1: Extend documentation tests before editing guidance**

Add tests that require:

```python
def test_public_and_runtime_guidance_links_the_capability_fixture(self) -> None:
    readme = self.text("README.md")
    runtime = self.text("RUNTIME_PROFILES.md")
    safety = self.text("SAFETY_AND_LIMITS.md")
    hermes = self.text("adapters/hermes-kanban.md")
    fixture = ROOT / "examples" / "capability-regression" / "README.md"
    self.assertTrue(fixture.is_file())
    self.assertIn("capability-regression", readme)
    self.assertIn("Capability Auditor", runtime)
    self.assertIn("capability_unproven", safety)
    self.assertIn("Mission Custodian", hermes)
    self.assertIn("Execution Coordinator", hermes)

def test_all_local_markdown_links_resolve(self) -> None:
    documents = (
        "README.md",
        "PROTOCOL.md",
        "AI_AGENT_INTEGRATION.md",
        "RUNTIME_PROFILES.md",
        "SAFETY_AND_LIMITS.md",
        "adapters/hermes-kanban.md",
        "examples/capability-regression/README.md",
    )
    pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
    for relative in documents:
        source = ROOT / relative
        for match in pattern.findall(source.read_text(encoding="utf-8")):
            target = match.split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            resolved = (source.parent / target).resolve()
            with self.subTest(source=relative, target=target):
                self.assertTrue(resolved.exists(), str(resolved))
```

Add `import re` to the test module. The test skips external and anchor-only
links, strips fragments, and resolves local targets relative to each Markdown
file's parent.

- [ ] **Step 2: Run the expanded documentation tests and confirm failure**

Run:

```bash
python3 tests/test_v03_documentation.py -v
```

Expected: FAIL because the new fixture README and guidance do not yet exist.

- [ ] **Step 3: Add runtime and safety rules**

In `RUNTIME_PROFILES.md`, add the Mission Contract and capability records to
authoritative state. Profile A uses local JSON plus a manually invoked offline
auditor; Profile B may schedule the auditor and publish results directly to the
operator-facing store; Profile C requires immutable shared evidence and scoped
probe credentials. Scheduled monitoring is optional and never replaces the
post-integration gate.

In `SAFETY_AND_LIMITS.md`, state that KLP cannot authorize live capability
probes. Unauthorized or unavailable probes produce `capability_unproven`.
Explain that safety constraints are valid but must prove they preserve affected
capabilities. Add claim limits preventing `completed` when a critical
capability is degraded or unproven.

- [ ] **Step 4: Upgrade the Hermes adapter**

Map the Mission Contract to a separately pinned immutable board artifact, not
the mutable root task body. Map the Execution Coordinator to the board manager,
the Mission Custodian to a separate named profile for critical work, and the
Capability Auditor to a dependent mechanical verifier whose result is written
to operator-visible evidence without coordinator rewriting.

Require Hermes to:

- load the canonical mission at task approval, repair, integration, and final
  review;
- compare changed surfaces to capability triggers;
- prevent board completion after a failed or inconclusive critical probe;
- create a blocked amendment task containing both required explanations;
- keep memory and conversation advisory rather than authoritative.

- [ ] **Step 5: Add the fixture README and public explanation**

Document exact offline commands:

```bash
output="$(mktemp -d)/klp-capability-fixture"
python3 examples/capability-regression/run_fixture.py --out-dir "$output"
python3 -m json.tool "$output/final-receipt.json"
```

Also document zero repair, inconclusive, and mission-mismatch invocations and
their exit codes.

Update the main README to v0.3 draft. In the 90-second version, begin by
freezing the product's core promise, then scope/build/check/criticize/integrate,
and finally prove the core promise again. Add this plain-language rule:

> Before agents change an app, prove it still does its main job. After they
> finish, prove it again. If it no longer works, the loop stops, even if every
> technical test passed.

Update the starter prompt to require mission identity, affected capabilities,
baseline evidence, and product-truth probes. Link both lifecycle fixtures and
state clearly that neither certifies production safety.

- [ ] **Step 6: Run documentation, fixture, and link tests**

Run:

```bash
python3 tests/test_v03_documentation.py -v
python3 examples/capability-regression/tests/test_contracts.py -v
python3 examples/capability-regression/tests/test_fixture.py -v
```

Expected: all tests PASS and all relative Markdown links resolve.

- [ ] **Step 7: Commit Task 6**

```bash
git add README.md RUNTIME_PROFILES.md SAFETY_AND_LIMITS.md adapters/hermes-kanban.md examples/capability-regression/README.md tests/test_v03_documentation.py
git commit -m "docs: publish KLP v0.3 operating guidance"
```

---

### Task 7: Combined Offline Verification And Design Conformance

**Files:**
- Verify only: all files changed by Tasks 1-6
- Modify only if a failing check exposes a defect within the approved design

**Interfaces:**
- Consumes: both lifecycle fixtures, critic harness, worker launcher, examples, and documentation tests.
- Produces: one evidence-backed implementation report tied to the exact final Git revision.

- [ ] **Step 1: Run every offline test suite from the repository root**

Run:

```bash
python3 examples/openai-compatible-critic/tests/test_critic.py -v
python3 examples/fail-review-repair/tests/test_fixture.py -v
python3 examples/capability-regression/tests/test_contracts.py -v
python3 examples/capability-regression/tests/test_fixture.py -v
python3 tests/test_v03_documentation.py -v
bash -n examples/deepseek-codex-worker/run.sh
```

Expected: every test PASS; no command requires external network or credentials.

- [ ] **Step 2: Exercise all fixture terminal paths directly**

Run each command with a new output directory:

```bash
python3 examples/capability-regression/run_fixture.py --out-dir "$(mktemp -d)/success"
python3 examples/capability-regression/run_fixture.py --out-dir "$(mktemp -d)/budget" --repair-round-limit 0
python3 examples/capability-regression/run_fixture.py --out-dir "$(mktemp -d)/unproven" --probe-mode inconclusive
python3 examples/capability-regression/run_fixture.py --out-dir "$(mktemp -d)/mismatch" --omit-capability-declaration
```

Expected exit codes in order: `0`, `3`, `4`, `5`.

- [ ] **Step 3: Regenerate records and verify a clean tree**

Run:

```bash
python3 examples/capability-regression/example_records.py
git diff --check
git status --short
```

Expected: regeneration creates no diff; `git diff --check` succeeds; status
contains no uncommitted implementation files.

- [ ] **Step 4: Review the combined artifact against the approved design**

Check every Acceptance Criteria bullet in
`docs/superpowers/specs/2026-09-03-klp-v0-3-capability-preservation-design.md`.
Record each as supported, unsupported, or not applicable with the exact test,
record, or document reference. Do not replace direct evidence with a model
summary.

- [ ] **Step 5: Prepare the final implementation report**

Report:

- exact final Git revision;
- commits created by each task;
- test commands and counts;
- successful and stopped fixture exit codes;
- no-external-network/no-paid-provider evidence;
- supported claims and limitations;
- whether GitHub push is still awaiting operator authorization.

Do not push, tag, publish, or change the public site as part of this plan unless
the operator separately authorizes that consequential action.
