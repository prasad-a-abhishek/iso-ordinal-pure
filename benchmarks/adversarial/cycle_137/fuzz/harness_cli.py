"""Atheris harness for the ``iso-ordinal-parse`` CLI (Surface 3).

The CLI is the user-facing entrypoint; fuzzing it covers argparse handling,
exit-code matrix (0 / 1 / 2 / argparse error), JSON payload emission, and
the manual BCE branch (``format`` returns ``-YYYY-DDD`` for negative years,
which argparse may interpret as a flag).

We invoke the CLI in a fresh subprocess so each fuzz input is fully isolated.
That means a crash in the CLI doesn't take down the fuzzer.

Exit-code contract (from src/iso_ordinal_parse/__main__.py):
* 0  — success (parse, validate-ok, version, no-args usage).
* 1  — ``--validate VALUE`` rejected VALUE (OrdinalDateParseError swallowed).
* 2  — argparse parse error (bad flag, unknown option).

Run:
    python3 harness_cli.py -atheris_runs=2000 -max_total_time=5

We cap ``atheris_runs`` low because each run is a subprocess spawn.
"""
from __future__ import annotations

import os
import subprocess
import sys

import atheris

# We don't instrument the CLI module — the fuzzer runs OUT of process.
# We DO need atheris to instrument this harness file itself so that
# coverage tracks the argv-construction branches here.
with atheris.instrument_imports():
    pass

# After instrumentation we can safely import the package for the version string.
from iso_ordinal_parse import __version__

# Use the installed module entry-point, not the in-tree ``__main__``.
# This mirrors what a real user would do (``pip install`` then ``python -m``).
_CMD = [sys.executable, "-m", "iso_ordinal_parse"]

# Build a child-env that keeps PATH and PYTHONPATH intact (so ``python -m
# iso_ordinal_parse`` can find the package) but forces unbuffered stdio.
_CHILD_ENV = {**os.environ, "PYTHONUNBUFFERED": "1"}


def _run_cli(argv: list[str], timeout: float = 1.0) -> subprocess.CompletedProcess:
    """Run the CLI with the given argv and return the CompletedProcess.

    We pass ``argv`` (a list) instead of relying on ``subprocess`` string
    parsing — this matches the in-process ``argparse.parse_args(argv)``
    contract.
    """
    return subprocess.run(
        _CMD + argv,
        capture_output=True,
        timeout=timeout,
        check=False,
        env=_CHILD_ENV,
    )


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Build a plausible argv.  We bound the size so subprocess spawn time
    # stays predictable and per-input timeout (5s) is realistic.
    mode = fdp.ConsumeIntInRange(0, 5)

    argv: list[str] = []
    try:
        if mode == 0:
            # Plain positional parse.
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = [raw]
        elif mode == 1:
            # --validate mode.
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = ["--validate", raw]
        elif mode == 2:
            # --validate=<value> mode (the docstring example for negative years).
            raw = fdp.ConsumeUnicodeNoSurrogates(20)
            argv = [f"--validate={raw}"]
        elif mode == 3:
            # --version flag (must succeed with exit 0).
            argv = ["--version"]
        elif mode == 4:
            # No arguments — CLI prints usage to stderr and exits 0.
            argv = []
        else:
            # Bogus flag to exercise argparse error branch (exit 2).
            fake_flag = "--definitely-not-a-real-flag-" + fdp.ConsumeUnicodeNoSurrogates(8)
            argv = [fake_flag]
    except UnicodeEncodeError:
        # FuzzedDataProvider may rarely yield lone surrogates; drop the input.
        return

    # Cap argv length so a single malformed token can't OOM the fuzzer.
    if len(argv) > 4:
        argv = argv[:4]

    try:
        proc = _run_cli(argv, timeout=1.0)
    except subprocess.TimeoutExpired:
        # 1s is generous for any well-formed input; a hang means the CLI
        # entered a real loop, which would be a bug.  Surface it by
        # propagating so atheris records the hang corpus entry.
        raise
    except (FileNotFoundError, PermissionError, OSError):
        # CLI not installed (developer machine without `pip install -e .`).
        # Skip this input rather than poisoning the corpus.
        return
    except ValueError as exc:
        # ``subprocess.run`` rejects argv containing embedded NUL bytes
        # with ``ValueError: embedded null byte`` BEFORE spawning the
        # child.  This is a CPython contract on POSIX, not a library
        # bug — skip the input.
        if "embedded null" in str(exc).lower():
            return
        raise

    rc = proc.returncode
    # Exit-code contract enforcement.
    if mode == 3:
        # --version always exits 0.
        assert rc == 0, f"--version exited {rc}: stderr={proc.stderr!r}"
        assert b"iso-ordinal-parse" in proc.stdout, f"--version missing version string: {proc.stdout!r}"
    elif mode == 4:
        # No args → usage on stderr, exit 0.
        assert rc == 0, f"no-args exited {rc}: stderr={proc.stderr!r}"
        assert b"usage:" in proc.stderr, f"no-args missing usage line: {proc.stderr!r}"
    elif mode == 5:
        # Unknown flag → argparse error, exit 2.
        assert rc == 2, f"unknown-flag exited {rc} (want 2): stderr={proc.stderr!r}"
        assert b"usage:" in proc.stderr.lower() or b"error:" in proc.stderr.lower(), (
            f"argparse error didn't mention usage/error: {proc.stderr!r}"
        )
    elif mode == 1:
        # --validate: 0 on valid, 1 on invalid.  Both are acceptable.
        assert rc in (0, 1), f"--validate exited {rc} (want 0 or 1): stderr={proc.stderr!r}"
    else:
        # mode 0 / 2: parse path.  Exit codes:
        #   0 — valid input, JSON emitted.
        #   1 — ``OrdinalDateParseError`` re-raised → Python prints
        #        traceback and exits 1 (deliberate per __main__.py line 91).
        #   2 — argparse error (only if the value starts with ``--``).
        # We accept 0, 1, 2 — any of these is a valid outcome.  We just
        # want to ensure the CLI doesn't exit with a non-standard code
        # (e.g. -11 SIGSEGV, or 3+ which would be a real bug).
        assert rc in (0, 1, 2), (
            f"parse path exited {rc} (want 0/1/2): stderr={proc.stderr!r}"
        )


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())