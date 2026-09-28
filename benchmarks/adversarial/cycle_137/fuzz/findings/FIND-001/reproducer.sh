#!/usr/bin/env bash
# FIND-001 reproducer — replays the crash-2d3118546140fbab4a780fc90283e49fe7b0b171
# input against harness_cli.py. Expects Atheris installed in the active Python
# interpreter and iso_ordinal_parse importable (PYTHONPATH=src handles the
# in-tree package).
#
# Exit code: 77 (libFuzzer "fuzz target exited"). stdout contains the full
# AssertionError stack trace from harness_cli.py line 135.

set -euo pipefail

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../../../../../.." && pwd)"
CRASH_INPUT="${REPO_ROOT}/benchmarks/adversarial/cycle_137/fuzz/findings/FIND-001/minimized_input"

cd "${REPO_ROOT}"
PYTHONPATH=src python3 benchmarks/adversarial/cycle_137/fuzz/harness_cli.py \
    -atheris_runs=1 -max_total_time=3 \
    "${CRASH_INPUT}"