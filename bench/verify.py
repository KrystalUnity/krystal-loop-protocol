#!/usr/bin/env python3
"""Recompute every published figure in this repository from its receipts. Offline, no API keys.

    python3 -m bench.verify            # every case study's checker
    python3 -m bench.verify --tests    # also the offline test suites for the runner and both benchmarks

Each case study keeps its own checker next to its receipts; this runs them all and prints one line each.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKERS = (
    ("Feature benchmark, 66 tasks", "case-studies/feature-benchmark-2026-11-10/verify.py"),
    ("Paired features and Semio, 30 pairs", "case-studies/paired-features-2026-11-10/verify.py"),
    ("Semio coordination study", "case-studies/semio-coordination-2026-10-20/verify.py"),
    ("SWE-bench Pro Ansible task", "case-studies/ansible-workers-2026-10-27/verify.py"),
    ("KrystalView repair", "case-studies/krystalview-2026-10-20/verify.py"),
)
TESTS = (
    ("Standard runner", "tests/test_standard_runner.py"),
    ("Feature benchmark harness", "tests/test_feature_benchmark.py"),
    ("Paired benchmark harness", "tests/test_pair_benchmark.py"),
    ("Documentation, links and published facts", "tests/test_v03_documentation.py"),
)


def run(items) -> int:
    failed = 0
    for label, script in items:
        done = subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, capture_output=True, text=True)
        if done.returncode == 0:
            print(f"ok    {label}")
        else:
            failed += 1
            print(f"FAIL  {label}")
            for line in (done.stdout + done.stderr).splitlines()[-12:]:
                print("      " + line)
    return failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tests", action="store_true", help="also run the offline test suites")
    args = parser.parse_args()
    failed = run(CHECKERS)
    if args.tests:
        failed += run(TESTS)
    print("\nEvery published figure recomputes from the receipts." if not failed else f"\n{failed} check(s) failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
