#!/usr/bin/env bash
# run_harnesses.sh — execute every Atheris harness in this directory with
# the Invariant 26 §2 timeout (5s per surface).
#
# Usage:
#   ./run_harnesses.sh          # 5s per harness (default)
#   ./run_harnesses.sh 30       # 30s per harness (deeper fuzzing)
#
# Environment:
#   PYTHONPATH must include ``src/`` (or the package must be installed).
#   The script will export it automatically if the package is importable
#   from a sibling ``src/`` directory.

set -euo pipefail

PER_HARNESS_SECONDS="${1:-5}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Layout: HERE/fuzz/cycle_137/adversarial/benchmarks/<REPO_ROOT>
# Four levels up gets us to the repo root.
REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"

# Ensure the package is importable.
if [[ -z "${PYTHONPATH:-}" ]] || ! python3 -c "import iso_ordinal_parse" 2>/dev/null; then
    if [[ -f "$REPO_ROOT/src/iso_ordinal_parse/__init__.py" ]]; then
        export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
    fi
fi

echo "==================================================================="
echo "cycle_137 adversarial fuzz sweep"
echo "  per-harness timeout: ${PER_HARNESS_SECONDS}s"
echo "  PYTHONPATH:          ${PYTHONPATH:-<unset>}"
echo "  python:              $(command -v python3) ($(python3 --version 2>&1))"
echo "  atheris:             $(python3 -c 'import atheris; print(getattr(atheris, "__version__", "installed"))' 2>&1)"
echo "==================================================================="

# Artifact directory for crashes/oom/hangs (atheris writes here).
ARTIFACT_DIR="$HERE/artifacts"
mkdir -p "$ARTIFACT_DIR"

# Run each harness.  We use ``timeout`` (coreutils) to enforce the
# per-harness wall-clock cap, and ``-atheris_runs`` to cap iterations
# so a single slow harness can't consume the whole sweep.
HARNESSES=(harness_parse.py harness_format.py harness_cli.py harness_dates.py)

for h in "${HARNESSES[@]}"; do
    if [[ ! -f "$HERE/$h" ]]; then
        echo "[skip] $h (not found)"
        continue
    fi
    echo "-------------------------------------------------------------------"
    echo "[run]  $h (timeout=${PER_HARNESS_SECONDS}s)"
    echo "-------------------------------------------------------------------"
    cd "$HERE"
    # We deliberately do NOT pass ``set -e`` semantics to this subshell —
    # atheris returning non-zero on a crash is exactly what we want to
    # see and report, not abort the sweep.
    set +e
    timeout "${PER_HARNESS_SECONDS}" python3 "$h" \
        -atheris_runs=100000 \
        -max_total_time="${PER_HARNESS_SECONDS}" \
        -artifact_prefix="$ARTIFACT_DIR/" \
        2>&1 | tail -20
    rc=$?
    set -e
    echo "[exit] $h -> rc=$rc"
    # Move any crash artifacts into a per-harness subdirectory so a
    # follow-up triage step can find them.
    if compgen -G "$ARTIFACT_DIR/crash-*" >/dev/null 2>&1; then
        mkdir -p "$ARTIFACT_DIR/crashes/$h"
        mv "$ARTIFACT_DIR"/crash-* "$ARTIFACT_DIR/crashes/$h/" 2>/dev/null || true
    fi
    if compgen -G "$ARTIFACT_DIR/oom-*" >/dev/null 2>&1; then
        mkdir -p "$ARTIFACT_DIR/oom/$h"
        mv "$ARTIFACT_DIR"/oom-* "$ARTIFACT_DIR/oom/$h/" 2>/dev/null || true
    fi
    if compgen -G "$ARTIFACT_DIR/timeout-*" >/dev/null 2>&1; then
        mkdir -p "$ARTIFACT_DIR/hangs/$h"
        mv "$ARTIFACT_DIR"/timeout-* "$ARTIFACT_DIR/hangs/$h/" 2>/dev/null || true
    fi
    # Also clean any crash files dropped in cwd (REPO_ROOT or HERE).
    rm -f crash-* oom-* timeout-*
done

echo "==================================================================="
echo "sweep complete"
echo "  artifacts: $ARTIFACT_DIR"
echo "==================================================================="