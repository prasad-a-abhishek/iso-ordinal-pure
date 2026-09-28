# FIND-001 (CLI-A1) — argparse positional slot swallows `--flag-with-trailing-space`

## Severity
**Info.** This is not a library bug; it is a documented argparse behaviour that
the harness incorrectly modelled and a UX polish opportunity on the CLI. No
memory unsafety, no correctness bug in `parse()`/`format()`/`to_date()`/
`from_date()`/`is_leap_year()`, no data loss, no security boundary violated.

## Surface
CLI entrypoint (`python -m iso_ordinal_parse`, served by
`src/iso_ordinal_parse/__main__.py`).

## Minimized input
Raw bytes (4 bytes): `02 20 00 35` (ASCII-decoded: `\x02 \x005`).

When fed to `atheris.FuzzedDataProvider` in `harness_cli.py::TestOneInput`,
this input produces:
* `mode = 5` (consumed by `ConsumeIntInRange(0, 5)`)
* `fake_flag = "--definitely-not-a-real-flag- "` (consumed by
  `ConsumeUnicodeNoSurrogates(8)` — the trailing space is the critical
  character; tab, newline, and digits at the same position do NOT trigger
  the bug, verified empirically with `python3 -m iso_ordinal_parse`).
* `argv = ['--definitely-not-a-real-flag- ']`

The 4-byte payload cannot be reduced: bisection to 1/2/3 bytes drops out
of the FDP path entirely (the fuzzer returns rc=0 with no harness body
executed). The 4-byte form is the lexicographically smallest payload that
yields both mode=5 AND a token containing a space character.

## Root cause
`__main__.py::_build_parser()` declares a positional `value` argument
(`nargs="?"`). When `argparse` sees a token that starts with `--` but does
NOT match any defined option AND contains no `=` separator AND contains
whitespace, the standard CPython argparse behaviour is to:

1. Fail to match the token as an option (because the leading `--` prefix
   makes it look like a flag, but no flag with that prefix is defined),
2. Fall through to positional handling, accepting the entire token as the
   positional value (whitespace and all).

The CLI then receives `target = '--definitely-not-a-real-flag- '` and
hands it to `parse()`. `parse()` correctly raises
`OrdinalDateParseError("bad format: expected YYYY-DDD, got '--definitely-not-a-real-flag- '")`.
Because `args.validate is None`, `__main__.py` line 91 (`raise`) re-raises
the exception. Python's default uncaught-exception handler prints a traceback
to stderr and exits with **rc=1**, not the rc=2 that `harness_cli.py`
asserted.

For comparison, `--definitely-not-a-real-flag-x` (no embedded whitespace)
IS cleanly rejected by argparse with rc=2 — that path is also exercised by
the fuzzer (mode==5 branch hit thousands of times during the T2 sweep).

## Reproduction
From the cycle_137 adv worktree:

```bash
PYTHONPATH=src python3 -m iso_ordinal_parse '--definitely-not-a-real-flag- '
# rc=1
# stderr: Traceback (most recent call last):
#   File "<frozen runpy>", line 198, in _run_module_as_main
#   ...
#   File ".../__main__.py", line 86, in main
#     ordinal = parse(target)
#   ...
# iso_ordinal_parse._iso_ordinal_parse.OrdinalDateParseError:
#   bad format: expected YYYY-DDD, got '--definitely-not-a-real-flag- '
```

Compare to the working rejection path:

```bash
PYTHONPATH=src python3 -m iso_ordinal_parse --definitely-not-a-real-flag-x
# rc=2
# stderr: usage: iso-ordinal-parse [-h] [--validate VALUE | VALUE] [--version]
# ...
#        iso-ordinal-parse: error: unrecognized arguments:
#        --definitely-not-a-real-flag-x
```

## Why it's not a library bug
* `parse()` correctly rejects `'--definitely-not-a-real-flag- '` (the input
  really is not an ordinal date).
* The exit code (1 vs 2) is a CLI UX choice, not a library contract.
* `argparse`'s positional-fallback behaviour is documented and stable
  across CPython versions.
* T1 (vuln_audit) already verified that `parse()` raises
  `OrdinalDateParseError` on every category of malformed input without
  any uncaught exception escaping from `iso_ordinal_parse`'s own modules.

## Why the harness crashed
`harness_cli.py` line 135 (`assert rc == 2, ...`) was too strict: it
assumed argparse would always cleanly reject any `--`-prefixed unknown
flag. The documented argparse behaviour (fall-through to positional slot
for `--flag-with-whitespace`) violates that assumption. The fix in a
future harness revision is to accept `rc ∈ {1, 2}` for the `mode==5`
branch — that's a harness contract change, not a library change.

## Severity rationale
| Severity | Definition | Applies? |
|---|---|---|
| Critical | exploitable memory corruption, RCE, data loss | No — no memory unsafety, no input touches non-library code. |
| High | crashes, hangs, OOM on benign input; silent wrong output | No — the CLI exits 1 with a traceback; parse() raises the documented exception; output is "nothing" rather than "wrong". |
| Medium | performance degradation; minor logic gaps | No — no perf impact, no logic gap inside `parse()`. |
| Low | cosmetic issues, edge cases with graceful but unexpected behavior | Close, but the traceback instead of a clean error message IS the entire user-visible symptom. |
| Info | observations, design choices, future hardening | **Yes** — this is a documented CPython behaviour; the workarounds (see below) are CLI UX polish, not bug fixes. |

## Recommendations (proposed for T5 / future cycles)
1. **CLI UX (preferred):** in `__main__.py::main()`, wrap the `parse()`
   call in `try/except OrdinalDateParseError:` and on the default (parse)
   path print a clean error message to stderr and `return 2` instead of
   re-raising. The `--validate` path already does this (returns 1).
2. **CLI UX (alternative):** subclass `argparse.ArgumentParser` to
   reject any token that starts with `--` but does not match a defined
   option BEFORE the positional slot accepts it. This also catches
   `-unknown-short-flag-with-space` etc.
3. **Harness UX:** relax `harness_cli.py` line 135 from
   `assert rc == 2` to `assert rc in (1, 2)`. After this change, the
   CLI surface can be fuzzed to completion (1M iters) instead of
   halting at iter ~2000. This is the lowest-risk path forward and
   isolates the change to the test harness.

None of these change library behaviour. The repo remains shippable as-is.

## Artifacts
* `minimized_input` — 4-byte raw crash artifact (already minimal)
* `stack_trace.txt` — full AssertionError + libFuzzer exit (re-captured 2026-09-28)
* `reproducer.sh` — deterministic replay script
* `description.md` — this file

## Cross-references
* `benchmarks/adversarial/cycle_137/CORPUS_RUN.md` §5.1 — T3 finding narrative
* `benchmarks/adversarial/cycle_137/fuzz/logs/cli_rerun_stdout.log` — original T3 stack trace
* `benchmarks/adversarial/cycle_137/fuzz/logs/cli_rerun_stderr.log` — Atheris coverage trace ending in the crash
* `benchmarks/adversarial/cycle_137/fuzz/crashes/cli/` — T3 crash quarantine dir (re-run crash)
* `benchmarks/adversarial/cycle_137/fuzz/crashes/cli_first_run/` — T3 first-run crash (same finding, different seed)