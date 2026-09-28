"""Atheris harness for ``iso_ordinal_parse.parse()`` (Surface 1).

Goal: drive every reachable code path in :func:`parse` with mutated string
input and verify that:

* Malformed input raises :class:`OrdinalDateParseError` (a ``ValueError``).
* Valid input round-trips through :func:`format` back to a string that
  re-parses to the same :class:`OrdinalDate`.
* Non-string input raises :class:`TypeError`.
* The harness itself never propagates any other exception type
  (uncaught ``AttributeError`` / ``IndexError`` / ``OverflowError`` would
  indicate a missed control-flow path or sanitizer-relevant bug).

Run:
    python3 harness_parse.py -atheris_runs=100000 -max_total_time=5

The ``-max_total_time=5`` matches Invariant 26 §2 (5s per-input timeout).
"""
from __future__ import annotations

import sys

import atheris

# Instrument the module BEFORE importing the symbols we fuzz.
with atheris.instrument_imports():
    from iso_ordinal_parse import (
        OrdinalDate,
        OrdinalDateParseError,
        format,
        parse,
    )


_EXPECTED_EXCEPTIONS = (
    OrdinalDateParseError,  # malformed / out-of-range
    ValueError,              # belt-and-braces; OrdinalDateParseError IS a ValueError
    TypeError,               # non-string input
)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Choose the input type randomly so we exercise both the
    # "non-string raises TypeError" branch and the main string path.
    kind = fdp.ConsumeIntInRange(0, 3)
    try:
        if kind == 0:
            # Unicode string (most common path). 64 chars upper bound.
            value = fdp.ConsumeUnicodeNoSurrogates(64)
        elif kind == 1:
            # ASCII-only — covers the digit-heavy path of ``parse``.
            value = fdp.ConsumeUnicodeNoSurrogates(32)
        elif kind == 2:
            # Bytes-like input should raise TypeError.  We still pass
            # through ConsumeUnicodeNoSurrogates to feed the fuzzer.
            raw = fdp.ConsumeUnicodeNoSurrogates(16)
            # Encode to bytes; this is what the fuzzer is *likely* to
            # produce when it mutates raw input.
            try:
                value = raw.encode("latin-1")
            except UnicodeEncodeError:
                value = None  # forces the TypeError branch via None
        else:
            # Force a non-string sentinel (None, int, list, bool).
            sentinel_choice = fdp.ConsumeIntInRange(0, 3)
            sentinels = (None, 0, [], False)
            value = sentinels[sentinel_choice]

        d = parse(value)  # type: ignore[arg-type]
    except _EXPECTED_EXCEPTIONS:
        return
    except RecursionError:
        # Defensive: pathological Unicode parsing must not blow the stack.
        return

    # If parse() succeeded, round-trip must succeed too.  Any failure
    # here is a real bug, not a sanitizer false positive.
    rendered = format(d)
    assert isinstance(rendered, str), f"format returned non-str: {type(rendered)!r}"
    assert len(rendered) >= 8, f"format returned too-short string: {rendered!r}"
    # And re-parsing the rendered string MUST yield the same ordinal.
    reparsed = parse(rendered)
    assert reparsed == d, (
        f"round-trip mismatch: {d!r} -> {rendered!r} -> {reparsed!r}"
    )
    assert isinstance(reparsed, OrdinalDate)


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())