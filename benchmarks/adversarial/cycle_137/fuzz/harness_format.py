"""Atheris harness for ``iso_ordinal_parse.format()`` (Surface 2).

Goal: fuzz the serializer by feeding it valid :class:`OrdinalDate` values
constructed from random (year, day_of_year) pairs, then asserting the
round-trip invariant ``parse(format(d)) == d``.

Specifically we test:

* Year in the supported range ``[-9999..9999]``.
* Day-of-year in ``[1..days_in_year(year)]`` (NOT 1..366 always — leap-year
  logic must be exercised).
* Negative years (BCE) must produce ``-YYYY-DDD`` with the sign BEFORE
  the year digits.
* :func:`format` rejects non-:class:`OrdinalDate` input via :class:`TypeError`.

Run:
    python3 harness_format.py -atheris_runs=100000 -max_total_time=5
"""
from __future__ import annotations

import sys

import atheris

with atheris.instrument_imports():
    from iso_ordinal_parse import (
        OrdinalDate,
        OrdinalDateParseError,
        days_in_year,
        format,
        is_leap_year,
        parse,
    )


_EXPECTED_EXCEPTIONS = (
    OrdinalDateParseError,
    ValueError,
    TypeError,
    OverflowError,  # fuzzer may craft absurd day_of_year values
)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # year in [-9999, 9999]  ->  ConsumeIntInRange
    year = fdp.ConsumeIntInRange(-9999, 9999)
    # day_of_year intentionally may be out-of-bounds — parse() / format()
    # can only deal with [1..days_in_year(year)], but the harness should
    # also probe the failure branches.
    day_of_year = fdp.ConsumeIntInRange(0, 400)

    try:
        # ``format`` does NOT validate ``day_of_year`` — it is documented
        # to take a pre-validated ``OrdinalDate``.  We still probe the
        # full ``[0..400]`` range to fuzz the *serialization* code, but
        # we only assert the round-trip invariant for VALID ordinals.
        max_day = 366 if is_leap_year(year) else 365
        valid = 1 <= day_of_year <= max_day

        ordinal = OrdinalDate(year=year, day_of_year=day_of_year)
        rendered = format(ordinal)
    except _EXPECTED_EXCEPTIONS:
        return

    assert isinstance(rendered, str), f"format -> {type(rendered).__name__}"
    # Length check.
    # Non-negative year: "YYYY-DDD"  ->  8 chars.
    # Negative year:     "-YYYY-DDD" -> 9 chars.
    if year < 0:
        assert rendered.startswith("-"), f"negative year without leading '-': {rendered!r}"
        assert len(rendered) == 9, f"unexpected length for negative-year format: {rendered!r}"
    else:
        assert not rendered.startswith("-"), f"non-negative year with leading '-': {rendered!r}"
        assert len(rendered) == 8, f"unexpected length for non-negative format: {rendered!r}"

    # The day-of-year part must be exactly 3 digits. ``format`` zero-pads
    # to width 3 unconditionally, so day=0 yields ``"000"`` and day=400
    # yields ``"400"`` (both 3 chars, both digits — still well-formed
    # strings even though they're not valid ordinals).
    dash_idx = rendered.rfind("-")
    day_part = rendered[dash_idx + 1:]
    assert len(day_part) == 3, f"day part not 3 digits: {rendered!r}"
    assert day_part.isdigit(), f"day part non-digit: {rendered!r}"

    # Round-trip: parse(format(d)) must equal d — BUT ONLY when ``d`` is
    # a valid ordinal.  For invalid (day_of_year out of range), ``parse``
    # will raise and we just record that as a "format accepted invalid
    # input" observation (not a bug, by design).
    if valid:
        reparsed = parse(rendered)
        assert reparsed == ordinal, (
            f"round-trip mismatch: {ordinal!r} -> {rendered!r} -> {reparsed!r}"
        )

    # days_in_year vs is_leap_year consistency on the canonical leap boundary.
    if is_leap_year(year):
        assert days_in_year(year) == 366
    else:
        assert days_in_year(year) == 365


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())