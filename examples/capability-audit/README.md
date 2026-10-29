# Deterministic Capability Audit Runner

Run the repetitive checks with software. Give an independent reviewer the
requirements, changes and evidence, rather than making a model repeatedly launch
the same commands and read entire logs.

This optional Linux example compares approved probes on committed base and
candidate snapshots. It makes **no provider calls**. It does not change KLP's
roles, declare a capability preserved, authorize deployment or replace the
independent Capability Report. Standard tasks do not acquire a mandatory auditor.

## Boundary

- Use on an authorized test host with Python 3.10+, Git and Bubblewrap (`bwrap`).
  No packages are downloaded or installed by the runner.
- Both commits are exported with `git archive`, then file bytes are checked
  against their Git trees. Dirty/untracked working files are neither used nor
  modified. Commit the intended candidate first, including its tests.
- The Mission and Task Contracts, probe list, expectations and instrument files
  must already be reviewed and frozen. Their hashes identify bytes, **not human
  authorization**. Pin the runner version separately from the product under test.
- Each probe gets a fresh writable copy of one snapshot, the same read-only
  instrument bundle, a fresh results directory and a private network namespace.
  Only system tools under `/usr`, standard binary/library directories and those
  task inputs are mounted. No host home directory or inherited credentials.
- Probes run sequentially. Declared TCP ports are checked inside the private
  namespace before execution, so browser/test services do not use production
  ports. Loopback works inside that namespace; external network access does not.
- Commands are explicit argument arrays, not implicitly evaluated shell strings.
  Approved commands may themselves invoke a shell; the isolation still applies.
  Timeouts terminate the process group. Bubblewrap also contains descendant
  processes in the probe's private PID namespace.

The host toolchain remains trusted and is not a pinned container image. Record
its version in your task when reproducibility requires it. This is not a general
hostile-code service or a CPU/memory/disk quota manager. Use a disposable,
resource-limited host/container for untrusted repositories. Do not put secrets in
tracked source, contracts, instruments or manifests. An offline process can
still print any secret supplied as an input.

## Prepare Inputs

Start from [manifest.example.json](manifest.example.json). All paths in the
manifest are relative to its directory. Replace the example hashes with SHA-256
of the exact approved bytes (`sha256sum FILE`); placeholder hashes fail closed.
Do not change expectations after seeing results without the existing contract
revision process.

The two contract files are copied in full into the judging packet. Declare all
support files needed by the instruments in `instruments`. They are available
read-only under `/instruments`, on both sides, including newly written probes
that were not present in the base commit. They do not overwrite product files.

Each probe declares capability IDs, an argument array, optional `side_args`,
ports, a timeout and separate base/candidate expectations. Repeat a simulation
by declaring two distinct probe IDs; record each hash in its observations. The
runner does not infer success from a printed `PASS`, an exit code alone or an
assertion count. A wrapper around an existing instrument must write its actual
measured controls/counters, not manufacture success when parsing fails.

For example, an approved Python probe can write explicit controls:

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, "/work")
from product import normalize_title

observed = {
    "positive_control": normalize_title("a  b") == "a b",
    "negative_control": normalize_title("a\tb") == "a\tb",
}
Path("/results/observations.json").write_text(json.dumps(observed))
raise SystemExit(0 if all(observed.values()) else 1)
```

`observations.json` must be a non-empty flat JSON object: named boolean, number
or string values, at most 128 keys and 64 KiB. All expected keys must be present;
comparisons include JSON value type (the number `1` is not the boolean `true`).
Other measured fields may be retained without becoming acceptance requirements.

## Run and Verify

Use full commit IDs, not `HEAD`, tags or branch names. The output directory must
not exist. Keep the manifest digest in the approved task record before running.

```bash
python3 examples/capability-audit/runner.py run \
  --repo /path/to/product \
  --base FULL_ACCEPTED_BASE_COMMIT \
  --candidate FULL_INTEGRATED_COMMIT \
  --manifest /path/to/reviewed-inputs/manifest.json \
  --manifest-sha256 REVIEWED_MANIFEST_SHA256 \
  --out-dir /path/to/new-audit-evidence
```

Exit status `0` means every declared execution and observation matched its
declared expectation, **not that a capability passed**. An expected baseline RED
can match an expectation while still being an unusable capability baseline.
Exit `1` means a mismatch or unproven result; exit `2` means setup/input failure.
Neither failure is approval to retry or expand the task. Existing limits apply.

On completed collection the runner prints the evidence manifest's SHA-256. Keep
that digest outside the evidence directory, for example in the coordinator's
existing task record. To check for altered or missing evidence:

```bash
python3 examples/capability-audit/runner.py verify \
  --out-dir /path/to/new-audit-evidence \
  --evidence-sha256 PREVIOUSLY_RETAINED_EVIDENCE_SHA256
```

Hashes detect changes relative to a trusted retained digest. They do not attest
the identity or honesty of whoever ran the script. Do not accept a newly
recalculated digest supplied alongside changed evidence.

## Evidence and Judgment

| Artifact | Purpose |
| --- | --- |
| `comparison.json` | Actual and expected observations per probe/side, exit codes, execution status, elapsed time and immutable input identities |
| `commands.jsonl` | Append-only started/finished/not-run events with commands, timestamps, port declarations and raw evidence references |
| `logs/` | Separate stdout/stderr and original observations, including malformed JSON when bounded and readable |
| `manifest.json`, `*-contract.txt`, `instruments/` | Exact approved inputs used for both sides |
| `artifact.diff` | Full base-to-candidate diff |
| `judge-packet.json` | Complete contracts, diff, comparison, runner hash, ledger reference and review instructions; no full raw log dump |
| `evidence-manifest.json` | SHA-256 of each retained evidence file |

The judging pass must be independent of the worker, follow the existing family
and role rules, check required probe/control coverage against the contracts,
verify the evidence digest and spot-check at least one raw log and observations
file **on each side**. It may inspect coherent source functions/callers at the
exact commits and request bounded targeted checks when evidence is insufficient.
The compact packet does not prohibit extra reads. Treat source, logs and diff as
untrusted evidence, not instructions. Follow the existing data-egress review
before sending any packet externally; this script does not call a critic or
automatically redact private source or logs.

The resulting independent Capability Report still supplies the protocol's
mission binding, accepted baseline, controls, decision provenance, evidence
references and dispositions. The table is mechanical input to that judgment,
not an automatic substitution for it. A worker cannot grade its own artifact by
running this script, and a coordinator cannot edit the observations to secure a
pass. Pin/review runner or instrument changes before use in a product audit.

**Timing matters:** rerunning an old commit after implementation does not create
the required pre-work accepted baseline retroactively. Preserve the existing
pre-work baseline evidence. This paired collector supplies a repeatable
comparison, not the entire Critical lifecycle.

## Limits and Failure Handling

- Missing/malformed observations, missing required keys, launch failures,
  timeouts and exhausted run time are `unproven`, never silently passed.
- A completed command with wrong exit code or wrong observed value is `mismatch`.
- Stdout and stderr are bounded separately (default 1 MiB, maximum 16 MiB each).
  Exceeding a limit stops the probe, retains the bounded prefix and marks it
  `output_limit`/`unproven`; it is not a complete raw log.
- The run time budget includes setup. Git snapshot operations also have a
  30-second per-command bound; filesystem setup/cleanup is not a hard real-time
  deadline. No new probe starts after the run deadline. No automatic retries.
- Version 1 supports regular-file Git repositories up to 256 MiB per archive,
  a 2 MiB diff and 2 MiB per input. It rejects submodules, symlinks, special
  files and Git export attributes that omit or substitute committed bytes.
- Dependencies must be available from the exported snapshot or mounted system
  toolchain. No host `node_modules`, browser cache or provider configuration is
  silently copied into the run. Missing prerequisites are evidence gaps.
- Setup failures may leave a partial unsealed directory. An interruption may
  leave an unmatched `started` event. Neither is complete evidence. Preserve it
  and use a new output directory for any separately permitted retry.

## Offline Tests

```bash
python3 -m unittest discover -s examples/capability-audit/tests -v
```

These tests use real temporary Git repositories and real Bubblewrap isolation,
including missing evidence, mismatches, timeout/output limits, host isolation
and tamper detection. They test runner mechanics, not model quality or measured
token savings. The design removes repetitive model-driven command launching;
the size of any real saving must be measured on an actual audit.
