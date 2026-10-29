# Real-Project Validation: 29 October 2026

## What Was Exercised

KU ran this optional collector against two frozen historical revisions of an
asset-heavy game repository. The full source and asset snapshot was about
523 MB. Existing browser, simulation, state and speech-service probes were
adapted to an offline Linux test environment without changing their assertions.
Each execution used a fresh private filesystem, process and network namespace.
The speech-service checks used a local fake service, not a live provider.

This is a sanitized first-party validation summary, not a public replay of the
private game or an independent external audit. Private source, contracts, raw
logs and application-specific adapters are not included. The public runner and
its offline tests are available for inspection and use on your own project.

Runner revision: `9eab054192efe3b8bc59428c6043ba2a48625531`.
Runner file SHA-256:
`98b70d004a381b5e3254e49431bf5659a23fd928f7043b98d1b81da8d900254c`.

## Results, Including the Failure

| Collection | Executions matching declared expectations | Elapsed seconds |
| --- | --- | --- |
| Preflight | 4 / 4 | 22.314512 |
| Main before/after comparison | 29 / 30 | 738.332137 |
| Bounded adapter correction and targeted repeat | 8 / 8 | 118.439484 |

All 15 candidate checks matched their declared expectations in the main run.
The older build reproduced six expected speech-service abuse-control failures;
the candidate passed all 11 controls in that probe. Browser end-to-end checks
passed 23/23 on each side, and four simulation runs produced the same hash.

One older-build abandoned-run telemetry probe initially passed only 5/7
controls, then passed 7/7 on the targeted repeat. The original failure remains
part of the evidence. The repeat does not erase it or establish its cause.

Independent review also caught unbounded output buffering in the private
adaptation wrapper. The wrapper was corrected to use the runner's bounded
capture. Four incorrect port labels were corrected, and only those four
affected probes were repeated on both versions. The generic runner was not
changed by this adapter repair. There was no third collection or product fix.

A separate Codex reviewer accepted the runner/adaptation for this bounded use,
but left complete product capability preservation **unproven** because the
baseline telemetry comparison was unstable. This was same-family review of
the Codex-authored adaptation; the original product work was authored by Claude.
No deployment or current release approval followed from these results.

## Effort and Interpretation

The collector performed 42 executions in 879.086133 seconds (14.65 minutes),
including preflight and the targeted repeat, with **zero model calls inside
collection**. That is collection time, not whole-job time or cost.

Preparation, portability work, review and corrections required model effort:

| Recorded checkpoint | Cumulative input tokens | Cached input subset | Output tokens | Top-level tool calls |
| --- | --- | --- | --- | --- |
| Coordinator through 02:21:09 UTC | 10,185,833 | 9,773,952 | 46,053 | 58 |
| Independent reviewer final | 1,964,270 | 1,862,400 | 12,604 | 21 |

Coordinator usage includes local protocol registry recovery, packaging, code,
tests and reporting, not merely audit judgment. It excludes subsequent closeout
and this publication task. Cumulative input counts repeated context; it is not
unique source content. Subscription cash allocation was unavailable, not zero.

The earlier model-driven audit was not a controlled, same-model comparison and
used different usage reporting. **This first adaptation did not establish net
token, time or cost savings.** Its demonstrated result is automated collection
on a real project, preserved failures and independent judgment. It does not
measure an incremental Semiotic Protocol benefit; the coordination adapter is
separate and optional.

## Verify the Public Mechanism

On an authorized Linux test host with Python 3.10+, Git and working Bubblewrap:

```bash
python3 -m unittest discover -s examples/capability-audit/tests -v
```

The 24 runner tests use temporary Git repositories and real isolation to check
observation matching, missing evidence, output/time limits, snapshot verification
and evidence tampering. They need no provider key. Follow the
[runner guide](README.md) to apply reviewed probes to your own frozen revisions.
Neither the tests nor this historical comparison replace a required pre-work
capability baseline or an independent acceptance decision.
