"""ISO 8601:2019 §4.4.2 ordinal date algorithm.

Pure-Python reference implementation. No third-party dependencies.

Public symbols (re-exported via ``iso_ordinal_parse.__init__``):

* :class:`OrdinalDate` — typed NamedTuple ``(year, day_of_year)``.
* :class:`OrdinalDateParseError` — raised on malformed input.
* :func:`parse` — parse a ``YYYY-DDD`` string into an :class:`OrdinalDate`.
* :func:`format` — canonical round-trip serializer.
* :func:`to_date` — convert to :class:`datetime.date`.
* :func:`from_date` — inverse of :func:`to_date`.
* :func:`is_leap_year` — Gregorian leap-year rule (proleptic).
* :func:`days_in_year` — 366 for leap years, else 365.

Year range: ``-9999`` .. ``9999`` (matches :class:`datetime.date` bounds).
Day-of-year range: ``1`` .. ``365`` (common) or ``1`` .. ``366`` (leap).
"""

from __future__ import annotations

import datetime as _datetime
from typing import NamedTuple

__all__ = [
    "OrdinalDate",
    "OrdinalDateParseError",
    "parse",
    "format",
    "to_date",
    "from_date",
    "is_leap_year",
    "days_in_year",
]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MIN_YEAR: int = -9999
_MAX_YEAR: int = 9999

# Cumulative day-of-year offset to the start of each month in a NON-LEAP year.
# Index 0 is January (offset 0); index 12 is December (offset 334 — the last
# index 12 means day 335 is the first day of December).
_NONLEAP_MONTH_OFFSETS: tuple[int, ...] = (
    0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334,
)
# Days in each month for a non-leap year.
_NONLEAP_MONTH_DAYS: tuple[int, ...] = (
    31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31,
)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class OrdinalDate(NamedTuple):
    """Typed ISO 8601 ordinal date value: ``(year, day_of_year)``.

    ``year`` is signed: negative years represent BCE dates per
    ISO 8601:2019 expanded representation. ``day_of_year`` is ``1``-based
    (1 = January 1) and is guaranteed to lie within the valid range for the
    given year (``1..365`` or ``1..366``).
    """

    year: int
    day_of_year: int


class OrdinalDateParseError(ValueError):
    """Raised when an input string cannot be parsed as an ISO 8601 ordinal date.

    The message identifies the specific failure mode:
    * ``"bad format"`` — input does not match ``YYYY-DDD`` or ``-YYYY-DDD``.
    * ``"day out of range"`` — day-of-year exceeds the year's day count.
    * ``"year out of range"`` — year is outside ``[-9999..9999]``.
    """


# ---------------------------------------------------------------------------
# Calendar helpers
# ---------------------------------------------------------------------------


def is_leap_year(year: int) -> bool:
    """Return ``True`` if ``year`` is a Gregorian leap year (proleptic).

    Rule: divisible by 4, except centuries unless by 400.

    >>> is_leap_year(2000)
    True
    >>> is_leap_year(1900)
    False
    >>> is_leap_year(2024)
    True
    >>> is_leap_year(2025)
    False

    Raises :class:`TypeError` if ``year`` is not an :class:`int` (``bool``
    is accepted because ``bool`` is a subclass of ``int``).
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError(
            f"is_leap_year() expected int, got {type(year).__name__}"
        )
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)


def days_in_year(year: int) -> int:
    """Return 366 if ``year`` is a leap year, else 365.

    Raises :class:`OrdinalDateParseError` if ``year`` is outside the supported
    range ``[-9999..9999]``. (This mirrors :class:`datetime.date`'s bounds.)
    Raises :class:`TypeError` if ``year`` is not an :class:`int`.
    """
    if not isinstance(year, int) or isinstance(year, bool):
        raise TypeError(
            f"days_in_year() expected int, got {type(year).__name__}"
        )
    if year < _MIN_YEAR or year > _MAX_YEAR:
        raise OrdinalDateParseError(
            f"year out of range: {year} not in [{_MIN_YEAR}..{_MAX_YEAR}]"
        )
    return 366 if is_leap_year(year) else 365


def _is_valid_int(s: str) -> bool:
    """Return True if ``s`` parses as a base-10 integer (no sign, no decimals)."""
    if not s:
        return False
    return all("0" <= c <= "9" for c in s)


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def parse(value: str) -> OrdinalDate:
    """Parse an ISO 8601 ordinal date string into an :class:`OrdinalDate`.

    Accepted forms (ISO 8601:2019 §4.4.2):

    * ``YYYY-DDD`` — basic format, e.g. ``"2026-271"``, ``"2024-366"``.
    * ``-YYYY-DDD`` — expanded form with negative year (BCE), e.g. ``"-0044-007"``.

    Raises :class:`OrdinalDateParseError` on malformed input or out-of-range
    day-of-year. Raises :class:`TypeError` on non-string input.
    """
    if not isinstance(value, str):
        raise TypeError(
            f"parse() expected str, got {type(value).__name__}"
        )

    s = value

    # Detect optional leading minus for expanded form.
    if s.startswith("-"):
        sign = -1
        body = s[1:]
    else:
        sign = 1
        body = s

    # Split into year / day at the single required dash separator.
    parts = body.split("-")
    if len(parts) != 2:
        raise OrdinalDateParseError(
            f"bad format: expected YYYY-DDD, got {value!r}"
        )

    year_str, day_str = parts

    # year_str may be 4 digits (e.g. "0044"); day_str must be exactly 3 digits.
    if len(year_str) != 4 or not _is_valid_int(year_str):
        raise OrdinalDateParseError(
            f"bad format: year part {year_str!r} must be exactly 4 digits"
        )
    if len(day_str) != 3 or not _is_valid_int(day_str):
        raise OrdinalDateParseError(
            f"bad format: day part {day_str!r} must be exactly 3 digits"
        )

    year = sign * int(year_str)
    day_of_year = int(day_str)

    if year < _MIN_YEAR or year > _MAX_YEAR:
        raise OrdinalDateParseError(
            f"year out of range: {year} not in [{_MIN_YEAR}..{_MAX_YEAR}]"
        )

    max_day = days_in_year(year)
    if day_of_year < 1 or day_of_year > max_day:
        raise OrdinalDateParseError(
            f"day out of range: day {day_of_year} not in 1..{max_day} for year {year}"
        )

    return OrdinalDate(year=year, day_of_year=day_of_year)


# ---------------------------------------------------------------------------
# Serializer (canonical round-trip)
# ---------------------------------------------------------------------------


def format(ordinal: OrdinalDate) -> str:
    """Format an :class:`OrdinalDate` to its canonical ISO 8601 string form.

    Produces ``YYYY-DDD`` for non-negative years and ``-YYYY-DDD`` (with the
    year zero-padded to 4 digits AFTER the sign) for negative years.

    >>> format(OrdinalDate(2026, 271))
    '2026-271'
    >>> format(OrdinalDate(-44, 7))
    '-0044-007'

    Raises :class:`TypeError` on non-:class:`OrdinalDate` input.
    """
    if not isinstance(ordinal, OrdinalDate):
        raise TypeError(
            f"format() expected OrdinalDate, got {type(ordinal).__name__}"
        )
    year, day = ordinal.year, ordinal.day_of_year
    if year < 0:
        return f"-{(-year):04d}-{day:03d}"
    return f"{year:04d}-{day:03d}"


# ---------------------------------------------------------------------------
# datetime.date conversion
# ---------------------------------------------------------------------------


def to_date(ordinal: OrdinalDate) -> _datetime.date:
    """Convert an :class:`OrdinalDate` to a :class:`datetime.date` (Gregorian).

    Implements the conversion via direct calendar math (NOT ``strptime``),
    so the result is validated against the actual Gregorian calendar.

    Note: :class:`datetime.date` only accepts years in the range
    ``1..9999``, so this function can only convert ordinals with
    ``year >= 1``. Negative (BCE) years raise
    :class:`OrdinalDateParseError` because the underlying ``date``
    constructor cannot represent them. Use :func:`format` for the
    canonical string representation of negative-year ordinals.
    """
    if not isinstance(ordinal, OrdinalDate):
        raise TypeError(
            f"to_date() expected OrdinalDate, got {type(ordinal).__name__}"
        )
    year = ordinal.year
    if year < 1:
        raise OrdinalDateParseError(
            f"to_date() cannot convert BCE year {year}: datetime.date only "
            f"supports years 1..9999; use format() for canonical string output"
        )
    day_of_year = ordinal.day_of_year

    # Days in months for the given year — handle February in leap years.
    month_days = list(_NONLEAP_MONTH_DAYS)
    if is_leap_year(year):
        month_days[1] = 29

    # Walk months until the remaining day-of-year fits in a month.
    remaining = day_of_year
    for month_idx, days_in_month in enumerate(month_days, start=1):
        if remaining <= days_in_month:
            return _datetime.date(year, month_idx, remaining)
        remaining -= days_in_month

    # Defensive — should never reach here because parse() validates day_of_year
    # against days_in_year(year). If we get here, something is inconsistent.
    raise OrdinalDateParseError(
        f"internal error: day {day_of_year} overflowed calendar for year {year}"
    )


def from_date(d: _datetime.date) -> OrdinalDate:
    """Convert a :class:`datetime.date` to its :class:`OrdinalDate` form.

    Uses ``(d - date(d.year, 1, 1)).days + 1`` so it works for negative years
    via the proleptic Gregorian calendar (Python's ``datetime.date`` arithmetic
    handles BCE dates correctly).
    """
    if not isinstance(d, _datetime.date):
        raise TypeError(
            f"from_date() expected datetime.date, got {type(d).__name__}"
        )
    year = d.year
    year_start = _datetime.date(year, 1, 1)
    day_of_year = (d - year_start).days + 1
    return OrdinalDate(year=year, day_of_year=day_of_year)