#!/usr/bin/env bash
# run_corpus.sh — cycle_137 T3 CORPUS_RUN driver.
#
# Runs each Atheris harness for ${PER_SURFACE_SECONDS:-120}s with the
# seed corpus, then collects per-surface counts of crash/oom/timeout
# artifacts dropped into the Atheris artifact directory.
#
# Usage:
#   ./run_corpus.sh                       # 120s per surface (default)
#   ./run_corpus.sh 60                    # 60s per surface (faster)
#
# Output structure (relative to fuzz/):
#   corpus_parse/, corpus_format/, corpus_cli/, corpus_dates/  -- seed corpus (input)
#   corpus/                                                    -- final fuzzer corpus (merged)
#   crashes/<surface>/                                         -- crash-* artifacts
#   hangs/<surface>/                                           -- timeout-* artifacts
#   oom/<surface>/                                             -- oom-* artifacts
#   logs/<surface>/stdout.log + stderr.log                     -- harness stdout/stderr
#   stats/<surface>.json                                       -- per-surface stats

set -uo pipefail

PER_SURFACE_SECONDS="${1:-120}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$HERE/../../../.." && pwd)"

# Ensure the package is importable.
if [[ -z "${PYTHONPATH:-}" ]] || ! python3 -c "import iso_ordinal_parse" 2>/dev/null; then
    if [[ -f "$REPO_ROOT/src/iso_ordinal_parse/__init__.py" ]]; then
        export PYTHONPATH="$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"
    fi
fi

echo "==================================================================="
echo "cycle_137 T3 CORPUS_RUN"
echo "  per-surface wall budget: ${PER_SURFACE_SECONDS}s"
echo "  PYTHONPATH:              ${PYTHONPATH:-<unset>}"
echo "  python:                  $(command -v python3) ($(python3 --version 2>&1))"
echo "  atheris:                 $(python3 -c 'import atheris; print(getattr(atheris, "__version__", "installed"))' 2>&1)"
echo "==================================================================="

mkdir -p "$HERE/corpus" \
         "$HERE/crashes" "$HERE/hangs" "$HERE/oom" \
         "$HERE/logs" "$HERE/stats"

# Atheris drops crash-* / oom-* / timeout-* files into the artifact
# directory when a finding fires.  We point each run at its own
# per-surface artifact dir so crashes are pre-quarantined.
run_surface() {
    local harness="$1"
    local surface="$2"

    local artifact_dir="$HERE/.artifacts_${surface}"
    local log_dir="$HERE/logs"
    local crash_dir="$HERE/crashes/${surface}"
    local hang_dir="$HERE/hangs/${surface}"
    local oom_dir="$HERE/oom/${surface}"

    mkdir -p "$artifact_dir" "$log_dir" "$crash_dir" "$hang_dir" "$oom_dir"

    echo "-------------------------------------------------------------------"
    echo "[run]  $harness (surface=$surface, wall=${PER_SURFACE_SECONDS}s)"
    echo "-------------------------------------------------------------------"

    local stdout_log="$log_dir/${surface}_stdout.log"
    local stderr_log="$log_dir/${surface}_stderr.log"
    local start end rc
    start=$(date +%s)

    # ``atheris.Fuzz()`` doesn't expose iteration counts via stderr the way
    # libFuzzer C targets do, but it does print a coverage summary on
    # normal exit.  We don't use ``set -e`` here — a non-zero rc is
    # exactly the signal we want to record.
    set +e
    # ``atheris.Fuzz()`` accepts the corpus directory as a positional argv
    # element (it forwards unknown args to libFuzzer).  We pass the
    # per-surface seed corpus here so the fuzzer starts from our seeds
    # rather than an empty corpus.
    timeout "${PER_SURFACE_SECONDS}" python3 "$HERE/$harness" \
        -atheris_runs=1000000 \
        -max_total_time="${PER_SURFACE_SECONDS}" \
        -artifact_prefix="${artifact_dir}/" \
        "$HERE/corpus_${surface}" \
        1>"$stdout_log" 2>"$stderr_log"
    rc=$?
    set -uo pipefail

    end=$(date +%s)
    local duration=$((end - start))

    echo "  rc=$rc  duration=${duration}s"

    # Quarantine artifacts.
    local crashes=0 hangs=0 ooms=0
    if compgen -G "$artifact_dir/crash-*" >/dev/null 2>&1; then
        crashes=$(ls -1 "$artifact_dir"/crash-* 2>/dev/null | wc -l)
        mv "$artifact_dir"/crash-* "$crash_dir"/ 2>/dev/null || true
    fi
    if compgen -G "$artifact_dir/timeout-*" >/dev/null 2>&1; then
        hangs=$(ls -1 "$artifact_dir"/timeout-* 2>/dev/null | wc -l)
        mv "$artifact_dir"/timeout-* "$hang_dir"/ 2>/dev/null || true
    fi
    if compgen -G "$artifact_dir/oom-*" >/dev/null 2>&1; then
        ooms=$(ls -1 "$artifact_dir"/oom-* 2>/dev/null | wc -l)
        mv "$artifact_dir"/oom-* "$oom_dir"/ 2>/dev/null || true
    fi

    # Also clean any crash files dropped in cwd (defensive — Atheris may
    # write into cwd if ``-artifact_prefix`` is missing trailing slash).
    rm -f crash-* oom-* timeout-*

    # Extract final coverage numbers from the Atheris coverage summary
    # line, which goes to stderr.  The line looks like (latest entries
    # near the end of the run):
    #     "#3272\tREDUCE cov: 22 ft: 22 corp: 8/22b lim: 29 exec/s: 0 rss: 43Mb L: 3/7 MS: ..."
    # or, on graceful exit:
    #     "Done 100000 in 0 second(s)"
    # We want the last line that contains "cov:" — it has the final tally.
    local cov="?" ft="?" execs="?" done_its=""
    local line
    line=$(grep -E '#?[0-9]+\s+(INITED|NEW|REDUCE)\s+cov: [0-9]+ ft: [0-9]+' "$stderr_log" 2>/dev/null | tail -1 || true)
    if [[ -n "$line" ]]; then
        cov=$(echo "$line" | sed -nE 's/.*cov: ([0-9]+).*/\1/p')
        ft=$(echo "$line" | sed -nE 's/.*ft: ([0-9]+).*/\1/p')
        execs=$(echo "$line" | sed -nE 's/^#([0-9]+).*/\1/p')
    fi
    # If we hit atheris_runs cap, the "Done N in M second(s)" line has the truth.
    local done_line
    done_line=$(grep -E '^Done [0-9]+ in [0-9]+' "$stderr_log" 2>/dev/null | tail -1 || true)
    if [[ -n "$done_line" ]]; then
        done_its=$(echo "$done_line" | sed -nE 's/^Done ([0-9]+) in.*/\1/p')
        [[ -n "$done_its" ]] && execs="$done_its"
    fi

    # Write per-surface stats.
    python3 - <<PYSTATS
import json, os

cov_raw = "${cov}"
ft_raw = "${ft}"
execs_raw = "${execs}"
cov = int(cov_raw) if cov_raw.isdigit() else None
ft = int(ft_raw) if ft_raw.isdigit() else None
execs = int(execs_raw) if execs_raw.isdigit() else None

stats = {
    "surface": "${surface}",
    "harness": "${harness}",
    "duration_seconds": ${duration},
    "rc": ${rc},
    "crashes": ${crashes},
    "hangs": ${hangs},
    "oom": ${ooms},
    "iters": execs,
    "coverage": cov,
    "feature_count": ft,
    "stdout_log": "${stdout_log}",
    "stderr_log": "${stderr_log}",
    "wall_timeout": ${PER_SURFACE_SECONDS},
    "seed_corpus": "$HERE/corpus_${surface}",
}
with open("$HERE/stats/${surface}.json", "w") as f:
    json.dump(stats, f, indent=2)
PYSTATS

    echo "  crashes=${crashes} hangs=${hangs} oom=${ooms} cov=${cov} ft=${ft} execs=${execs}"
    echo "  stats -> $HERE/stats/${surface}.json"
    echo "  log   -> $stdout_log"
}

run_surface "harness_parse.py"  "parse"
run_surface "harness_format.py" "format"
run_surface "harness_cli.py"    "cli"
run_surface "harness_dates.py"  "dates"

# Aggregate cycle-level stats.
python3 - <<'PYAGG'
import json, os
stats_dir = os.environ.get("STATS_DIR", "stats")
agg = {
    "cycle": "137",
    "phase": "T3 CORPUS_RUN",
    "surfaces": [],
    "total_iters": 0,
    "total_crashes": 0,
    "total_hangs": 0,
    "total_oom": 0,
    "total_oracle_mismatches": 0,
    "surfaces_covered": [],
    "duration_seconds": 0,
}
for surf in ("parse", "format", "cli", "dates"):
    p = os.path.join(stats_dir, f"{surf}.json")
    if not os.path.exists(p):
        continue
    with open(p) as f:
        s = json.load(f)
    agg["surfaces"].append(s)
    agg["surfaces_covered"].append(surf)
    agg["total_crashes"] += s.get("crashes", 0)
    agg["total_hangs"]   += s.get("hangs", 0)
    agg["total_oom"]     += s.get("oom", 0)
    agg["duration_seconds"] += s.get("duration_seconds", 0)
    agg["total_iters"] += s.get("iters") or 0

with open("AGGREGATE_STATS.json", "w") as f:
    json.dump(agg, f, indent=2)
print("AGGREGATE_STATS.json written")
print(f"  total iters: {agg['total_iters']}")
print(f"  total crashes: {agg['total_crashes']}")
print(f"  total hangs:   {agg['total_hangs']}")
print(f"  total oom:     {agg['total_oom']}")
print(f"  surfaces:      {agg['surfaces_covered']}")
print(f"  duration:      {agg['duration_seconds']}s")
PYAGG

# Copy/move AGGREGATE_STATS.json into fuzz/stats for the deliverable path.
mv AGGREGATE_STATS.json stats/AGGREGATE_STATS.json

echo "==================================================================="
echo "sweep complete"
echo "  artifacts: $HERE/crashes  $HERE/hangs  $HERE/oom"
echo "  logs:      $HERE/logs"
echo "  stats:     $HERE/stats"
echo "==================================================================="
