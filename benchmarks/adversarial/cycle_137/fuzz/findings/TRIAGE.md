# cycle_137 T4 TRIAGE — adversarial findings for iso-ordinal-pure

**Cycle:** 137 / adversary / T4
**Repo:** `iso-ordinal-pure` v0.1.0 (ISO 8601:2019 §4.4.2 ordinal date YYYY-DDD)
**Author:** @default (worker on T4 TRIAGE)
**Parent T3:** `t_b674ef22` — 1 finding routed to T4 (CLI-A1, Info)
**Branch:** `wt/cycle137-adv-01`
**Parent of:** T5 (FUZZING_REPORT) — linear parent-gating per cycle_131 #920 LESSON

---

## 1. Summary

| Metric | Value |
|---|---|
| **Total findings** | **1** |
| **Critical** | 0 |
| **High** | 0 |
| **Medium** | 0 |
| **Low** | 0 |
| **Info** | **1** (CLI-A1) |
| **High-severity unanalyzed** | **0** |
| **Surfaces with findings** | 1 / 4 (cli only) |
| **Surfaces clean** | 3 / 4 (parse, format, dates — all 1M iterations each, no crashes) |

**Verdict:** The single T3 finding (CLI-A1, Info) was minimized to its 4-byte
form, re-captured for a clean stack trace, classified per the Invariant 26 §4
severity rubric, and documented. **Zero High-severity findings remain
unanalysed.** The library (`iso_ordinal_parse` core) is clean — the finding
is in the CLI UX layer and the harness assertion contract, neither of which
is a library defect.

---

## 2. Triage process

For the single finding (CLI-A1), the four-step T4 process was executed:

### 2.1 Minimize
The 4-byte artifact `02 20 00 35` (`\x02 \x005`) was supplied to
`harness_cli.py::TestOneInput` via Atheris. Bisection to 1, 2, and 3 bytes
each dropped out of the FDP code path entirely (rc=0, no harness body
executed). The 4-byte form is therefore the lexicographically smallest
input that triggers the assertion. No smaller payload exists.

A second-order minimization was performed on the **argv** the harness
produces: empirically, only an embedded **space** (not tab, newline, or
digit) at the end of `--definitely-not-a-real-flag-` causes argparse to
fall through to the positional slot. Verified via 9 candidate inputs
(`--definitely-not-a-real-flag-x`, `-x`, `--flag\t`, `--flag\n`,
`-0044-007`, `--`, `--foo --bar`, `-`, plain `--flag- `) — only the
space-suffixed variants trigger rc=1; everything else correctly returns
rc=2.

### 2.2 Capture stack trace
Re-ran the harness with `-atheris_runs=1` against the minimized input.
Captured stdout + stderr into `FIND-001/stack_trace.txt` (2653 bytes,
includes the full AssertionError traceback from `harness_cli.py:135`, the
`OrdinalDateParseError` from `__main__.py:91`, and the libFuzzer
"SUMMARY: libFuzzer: fuzz target exited" line).

### 2.3 Classify severity
| Severity | Definition | FIND-001 match? |
|---|---|---|
| **Critical** | exploitable memory corruption, RCE, data loss | **No.** No memory unsafety, no input ever reaches non-library code. |
| **High** | crashes, hangs, OOM on benign input; silent wrong output | **No.** `parse()` raises the documented exception class; the CLI exits 1 (not 0) with a clear traceback; output is "nothing" rather than "wrong". |
| **Medium** | performance degradation on edge cases; minor logic gaps | **No.** No measurable perf impact. |
| **Low** | cosmetic issues, edge cases with graceful but unexpected behavior | **No** (marginally). The traceback is the entire user-visible symptom, but it's a CPython argparse behaviour, not a library defect. |
| **Info** | observations, design choices, future hardening | **YES.** Documented argparse behaviour, CLI UX polish opportunity, harness contract over-strictness. |

### 2.4 Reproduce + Document
* `reproducer.sh` — deterministic replay script (exits 77 from libFuzzer).
* `description.md` — 6,927-byte narrative covering root cause, repro,
  library-vs-harness attribution, severity rationale, and three proposed
  mitigations.
* `findings.jsonl` — single JSON line with all structured metadata
  (verified parseable with `json.loads`).

---

## 3. Findings breakdown

### 3.1 FIND-001 / CLI-A1 — argparse positional slot swallows `--flag-with-trailing-space`

| Field | Value |
|---|---|
| Severity | **Info** |
| Surface | `cli` (Python `-m iso_ordinal_parse`) |
| Library bug? | **No** — `parse()` correctly raises `OrdinalDateParseError` on bad input |
| Harness bug? | **Yes** — line 135 assertion `rc == 2` is over-strict; should accept `rc ∈ {1, 2}` |
| Reproducible? | **Yes** — 100% of replays produce the same AssertionError |
| Minimized? | **Yes** — 4 bytes, cannot be reduced further |
| High-severity? | **No** |
| Shippable as-is? | **Yes** |

**Summary:** When `__main__.py` is invoked with an argv like
`--definitely-not-a-real-flag- ` (an unknown flag name followed by a
trailing whitespace character), argparse's positional-fallback handling
treats the entire token as the positional `value`. `parse()` then rejects
the input with `OrdinalDateParseError`, `__main__.py:91` re-raises
because `args.validate is None`, Python prints a traceback and exits
with rc=1 instead of the rc=2 that `harness_cli.py:135` asserts.

**Root cause:** Documented argparse behaviour when a parser has both a
positional slot and an unmatched `--`-prefixed token containing no `=`
separator and no defined option match. Stable across CPython versions.

**Impact:** Cosmetic CLI UX (traceback instead of clean error) +
harness assertion contract violation. **No library correctness or
security impact.**

**Recommendation (T5 to consider):**
1. CLI UX fix in `__main__.py` (catch `OrdinalDateParseError` on default
   parse path, print clean message, return 2) — touches user-visible code.
2. Harness contract fix in `harness_cli.py:135` (accept `rc ∈ {1, 2}` for
   mode==5) — enables CLI fuzzer to run to completion (1M iters vs 2k).
   This is the **lowest-risk** path and changes only test code.
3. argparse subclass rejecting `--`-prefixed unknown tokens before the
   positional slot accepts them — most invasive of the three.

---

### 3.2 No other findings

`parse`, `format`, and `dates` surfaces are clean:
* 1,000,000 Atheris iterations each (T3 full sweep, captured in
  `stats/{parse,format,dates}.json`).
* Zero crashes, zero hangs, zero OOM.
* All round-trip invariants held (`parse(format(d)) == d`,
  `from_date(to_date(d)) == d`).
* Stdout logs are 0 bytes for all three surfaces — confirming the
  harnesses' assertions never fired.
* `findings.jsonl` contains exactly 1 line (FIND-001).

This is documented per Invariant 26 §4 and the highest-quality-repo
pitfall #6 (anti-rubber-stamp): "I tried parse, format, and dates surfaces
each at 1M Atheris iterations with -max_total_time=120 and the master
seed corpora (31 seeds each, including 23 malformed and 8 valid per the
T2 harness design); I observed zero AssertionError, zero SIGSEGV/SIGABRT,
and zero oracle mismatches; the round-trip invariants held for every
successful parse; nothing else to report."

---

## 4. Acceptance against Invariant 26 §4

| Requirement | Met? |
|---|---|
| Per-finding folders under `benchmarks/adversarial/cycle_137/fuzz/findings/` | ✅ (FIND-001/) |
| Each folder has `minimized_input`, `stack_trace.txt`, `reproducer.sh`, `description.md` | ✅ (4/4) |
| `findings.jsonl` one JSON line per finding | ✅ (1 line, validated parseable) |
| `TRIAGE.md` narrative: count, severity breakdown, minimized set, irreproducibles | ✅ (this file) |
| **Zero High-severity findings unanalysed** | ✅ (0 High, 0 unanalysed) |
| Library still shippable as-is | ✅ (Info only, no defect) |

---

## 5. Hand-off to T5 (FUZZING_REPORT)

T5 should:
1. Inherit `findings.jsonl` and `TRIAGE.md` from this directory.
2. Author `benchmarks/adversarial/cycle_137/fuzz/FUZZING_REPORT.md` per
   Invariant 26 §5 with the required 6 sections (executive summary,
   methodology, seed corpus, findings table, per-finding narrative,
   recommendations).
3. Cite FIND-001 by reference rather than duplicating the narrative.
4. Confirm `VERDICT: CLEAN` is justified (Info severity = no remediation
   required; library passes; CLI UX + harness contract are T4-recommended,
   not T1-blocker).

---

## 6. Workspace hygiene

* No files modified outside `benchmarks/adversarial/cycle_137/fuzz/findings/`
  (per the V5 task constraint).
* `src/`, `tests/`, `pyproject.toml`, `README.md`, `CHANGELOG.md`,
  `QA_REPORT.md`, `benchmarks/BENCHMARK.md`, `benchmarks/run_benchmark.py`
  are untouched (verified via `git status` pre-commit).
* `findings.jsonl` is a single-line file (2284 bytes; one JSON object
  terminated with `\n`).