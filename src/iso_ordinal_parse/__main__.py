"""Command-line entry-point for ``iso-ordinal-pure``.

Three modes:

* Default: parse a positional argument, print JSON
  ``{"year": ..., "day_of_year": ..., "date": "YYYY-MM-DD"}`` to stdout.
* ``--validate VALUE``: exit 0 if ``VALUE`` is a valid ordinal date, else 1.
* ``--version``: print package version, exit 0.

Running with no arguments prints a short usage line to stderr (exit 0).
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import sys

from iso_ordinal_parse import (
    __version__,
    OrdinalDateParseError,
    is_leap_year,
    parse,
)

_PROGRAM = "iso-ordinal-parse"
_USAGE = (
    f"usage: {_PROGRAM} [-h] [--validate VALUE | VALUE] [--version]\n"
    f"\n"
    f"Parse an ISO 8601 ordinal date (YYYY-DDD).\n"
    f"\n"
    f"Examples:\n"
    f"  {_PROGRAM} 2026-271\n"
    f"  {_PROGRAM} --validate 2024-366\n"
    f"  {_PROGRAM} --validate=-0044-007   # use '=' for negative years\n"
    f"  {_PROGRAM} --version\n"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=_PROGRAM,
        description="Parse an ISO 8601 ordinal date (YYYY-DDD).",
        add_help=True,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "value",
        nargs="?",
        default=None,
        help="Ordinal date string to parse (e.g. 2026-271). Prefix with -- "
             "for negative years, e.g. -- -0044-007.",
    )
    parser.add_argument(
        "--validate",
        dest="validate",
        default=None,
        metavar="VALUE",
        help="Validate VALUE; exit 0 if valid, 1 if not. Ignored positional.",
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Print version and exit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"{_PROGRAM} {__version__}")
        return 0

    # Default (no args): short usage on stderr, exit 0.
    if args.validate is None and args.value is None:
        print(_USAGE, file=sys.stderr, end="")
        return 0

    target = args.validate if args.validate is not None else args.value

    try:
        ordinal = parse(target)
    except OrdinalDateParseError:
        if args.validate is not None:
            return 1
        # Re-raise when invoked as a normal parse — caller sees the reason.
        raise

    # --validate path: successful parse exits 0.
    if args.validate is not None:
        return 0

    # Default parse path: emit JSON.
    # For years >= 1, compute the calendar date via datetime arithmetic.
    # For years < 1 (BCE), datetime.date cannot represent them; emit the
    # date components computed manually using the same calendar math as
    # ``to_date`` (year, month, day) and format the ISO date string with a
    # negative-year prefix.
    if ordinal.year >= 1:
        cal_date = _datetime.date(ordinal.year, 1, 1) + _datetime.timedelta(
            days=ordinal.day_of_year - 1
        )
        date_str = cal_date.isoformat()
    else:
        # Manual month/day conversion for BCE years.
        # Days in months for the given year (proleptic Gregorian).
        month_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if is_leap_year(ordinal.year):
            month_days[1] = 29
        remaining = ordinal.day_of_year
        month_idx = 1
        for md in month_days:
            if remaining <= md:
                break
            remaining -= md
            month_idx += 1
        day = remaining
        date_str = f"-{(-ordinal.year):04d}-{month_idx:02d}-{day:02d}"

    payload = {
        "year": ordinal.year,
        "day_of_year": ordinal.day_of_year,
        "date": date_str,
    }
    print(json.dumps(payload, separators=(", ", ": ")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())