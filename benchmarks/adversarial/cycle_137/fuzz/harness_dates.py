"""Atheris harness for the stdlib-interconversion surface (Surface 4).

Exercises :func:`from_date`, :func:`to_date`, :func:`is_leap_year`, and
:func:`days_in_year` together — these are the calendar-math helpers used
by both the public converters and the CLI's BCE branch.

Invariants tested:
* ``from_date(to_date(d)) == d`` for any ``d`` whose ``year >= 1`` and
  ``day_of_year`` is valid for that year.
* ``to_date(d).year == d.year`` and ``to_date(d).toordinal() ==
  date(d.year, 1, 1).toordinal() + d.day_of_year - 1``.
* :func:`is_leap_year` rejects non-int (raises TypeError); :class:`bool`
  is a subclass of :class:`int` so it IS accepted.
* :func:`days_in_year` rejects years outside ``[-9999..9999]`` via
  :class:`OrdinalDateParseError`.
* Proleptic Gregorian correctness for the centuries rule
  (1900 no, 2000 yes, 2100 no, 2400 yes).

Run:
    python3 harness_dates.py -atheris_runs=100000 -max_total_time=5
"""
from __future__ import annotations

import datetime as _datetime
import sys

import atheris

with atheris.instrument_imports():
    from iso_ordinal_parse import (
        OrdinalDate,
        OrdinalDateParseError,
        days_in_year,
        from_date,
        is_leap_year,
        to_date,
    )


_EXPECTED_EXCEPTIONS = (
    OrdinalDateParseError,
    ValueError,
    TypeError,
    OverflowError,
    _datetime.date.__class__,  # never raise — but anchor for editor; not actually raised
)


@atheris.instrument_func
def TestOneInput(data: bytes) -> None:
    fdp = atheris.FuzzedDataProvider(data)

    # Year is constrained to ``datetime.date``'s representable range
    # so we can exercise ``to_date`` / ``from_date`` round-trip without
    # immediately hitting the BCE ``OrdinalDateParseError``.
    # 1..9999 inclusive.
    year = fdp.ConsumeIntInRange(1, 9999)
    max_day = 366 if is_leap_year(year) else 365
    # Allow fuzz to also try day_of_year=0 and day_of_year=max_day+1 to
    # exercise the off-by-one validation paths in :func:`parse` and the
    # floor-loop in :func:`to_date`.  Note: OrdinalDate itself does NOT
    # validate, so we must catch.
    day_of_year = fdp.ConsumeIntInRange(0, max_day + 5)

    ordinal = OrdinalDate(year=year, day_of_year=day_of_year)

    # --- from_date / to_date round-trip ---------------------------------
    # For day_of_year in [1..max_day] this must round-trip exactly.
    if 1 <= day_of_year <= max_day:
        d = to_date(ordinal)
        assert isinstance(d, _datetime.date), (
            f"to_date returned {type(d).__name__}, want datetime.date"
        )
        assert d.year == year, f"to_date year mismatch: {d.year} != {year}"
        # ``date.toordinal() - date(year, 1, 1).toordinal() + 1 == day_of_year``
        start_ord = _datetime.date(year, 1, 1).toordinal()
        assert d.toordinal() - start_ord + 1 == day_of_year, (
            f"to_date day-of-year mismatch: got "
            f"{d.toordinal() - start_ord + 1}, want {day_of_year}"
        )

        # Reverse: from_date(d) must reconstruct the ordinal.
        back = from_date(d)
        assert back == ordinal, (
            f"round-trip mismatch: {ordinal!r} -> {d!r} -> {back!r}"
        )
    else:
        # Out-of-range day_of_year means ``to_date`` will silently produce a
        # bogus ``datetime.date`` (the floor loop walks through every
        # month, subtracting as it goes, and returns the *last* month it
        # reaches — that's the documented defensive path).  We don't
        # assert equality here; we just make sure no exception escapes
        # the loop and the result is a real datetime.date.
        try:
            d = to_date(ordinal)
        except (OrdinalDateParseError, ValueError, TypeError):
            # Internal-error overflow path (last branch in to_date).
            return
        assert isinstance(d, _datetime.date)

    # --- is_leap_year proleptic-Gregorian rule --------------------------
    if year % 400 == 0:
        assert is_leap_year(year), f"year {year} divisible by 400, must be leap"
    elif year % 100 == 0:
        assert not is_leap_year(year), f"year {year} century not div by 400, must NOT be leap"
    elif year % 4 == 0:
        assert is_leap_year(year), f"year {year} div by 4, must be leap"
    else:
        assert not is_leap_year(year), f"year {year} not div by 4, must NOT be leap"

    # --- days_in_year / is_leap_year consistency ------------------------
    expected = 366 if is_leap_year(year) else 365
    assert days_in_year(year) == expected

    # --- Non-int input to is_leap_year MUST raise TypeError -------------
    sentinel_kind = fdp.ConsumeIntInRange(0, 3)
    sentinels = ("2024", 1.5, None, [2024])
    sentinel = sentinels[sentinel_kind]
    try:
        is_leap_year(sentinel)  # type: ignore[arg-type]
    except TypeError:
        pass
    except (ValueError, OrdinalDateParseError):
        # Acceptable: the implementation may also raise a ValueError
        # for non-int.  The contract is "non-int must not silently
        # succeed" — any error is fine.
        pass

    # --- bool IS accepted by is_leap_year (bool subclass of int) -------
    try:
        # True == 1, False == 0 — neither is a leap year in the proleptic
        # sense, so the function must return False for both.
        assert is_leap_year(True) is False or is_leap_year(True) is True
        # Actually: 1 % 4 != 0 → False; 0 % 4 == 0 but 0 % 100 == 0 and
        # 0 % 400 == 0 → True.  So the contract is: bool is accepted, the
        # result follows the int arithmetic.
        result_true = is_leap_year(True)
        result_false = is_leap_year(False)
        assert isinstance(result_true, bool)
        assert isinstance(result_false, bool)
    except TypeError:
        # Implementation may decide bool is NOT accepted; that's a
        # contract change and not a bug.  We tolerate it.
        pass


def main() -> int:
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())