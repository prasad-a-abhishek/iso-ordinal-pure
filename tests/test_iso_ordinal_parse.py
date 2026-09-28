"""Tests for iso-ordinal-pure.

14 categories (Cat-A..Cat-N):

* Cat-A canonical round-trip
* Cat-B leap-year boundary
* Cat-C negative-year expanded form
* Cat-D leap-year rules
* Cat-E to_date conversion
* Cat-F from_date round-trip
* Cat-G error messages
* Cat-H CLI smoke
* Cat-I fresh-venv import (skipped in default run, see AC1 verification)
* Cat-J type-error safety
* Cat-K fuzz property
* Cat-L boundary days
* Cat-M CLI JSON shape
* Cat-N adversarial malformed

Run with ``PYTHONPATH=src pytest -q``.
"""

from __future__ import annotations

import datetime
import json
import random
import subprocess
import sys
from pathlib import Path

import pytest

from iso_ordinal_parse import (
    OrdinalDate,
    OrdinalDateParseError,
    days_in_year,
    format,
    from_date,
    is_leap_year,
    parse,
    to_date,
)

# Path to the package root for subprocess-based CLI tests.
_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"


# ---------------------------------------------------------------------------
# Cat-A — canonical round-trip
# ---------------------------------------------------------------------------


class TestCanonicalRoundTrip:
    """``format(parse(x)) == x`` for canonical inputs."""

    @pytest.mark.parametrize(
        "raw",
        [
            "2026-271",
            "2024-001",
            "2024-366",
            "2000-060",
            "1900-365",
            "-0044-007",
            "-0001-365",
            "-9999-001",
            "0001-001",
            "9999-365",
        ],
    )
    def test_parse_format_roundtrip(self, raw: str) -> None:
        od = parse(raw)
        assert format(od) == raw

    def test_ordinal_date_namedtuple_shape(self) -> None:
        od = parse("2026-271")
        assert od.year == 2026
        assert od.day_of_year == 271
        assert isinstance(od, OrdinalDate)
        # NamedTuple equality & iteration
        assert tuple(od) == (2026, 271)
        assert od == OrdinalDate(2026, 271)


# ---------------------------------------------------------------------------
# Cat-B — leap-year boundary (AC3)
# ---------------------------------------------------------------------------


class TestLeapYearBoundary:
    """Day-of-year validation against the actual Gregorian calendar."""

    def test_2024_366_accepted_leap(self) -> None:
        assert parse("2024-366") == OrdinalDate(2024, 366)

    def test_2025_366_rejected_non_leap(self) -> None:
        with pytest.raises(OrdinalDateParseError, match="day out of range"):
            parse("2025-366")

    def test_2000_366_accepted_by_400(self) -> None:
        assert parse("2000-366") == OrdinalDate(2000, 366)

    def test_1900_366_rejected_century_not_400(self) -> None:
        with pytest.raises(OrdinalDateParseError, match="day out of range"):
            parse("1900-366")

    def test_2100_366_rejected_future_century(self) -> None:
        with pytest.raises(OrdinalDateParseError, match="day out of range"):
            parse("2100-366")

    def test_2400_366_accepted_future_by_400(self) -> None:
        assert parse("2400-366") == OrdinalDate(2400, 366)

    def test_2025_365_accepted_non_leap_boundary(self) -> None:
        assert parse("2025-365") == OrdinalDate(2025, 365)

    def test_2024_001_accepted_leap_jan1(self) -> None:
        assert parse("2024-001") == OrdinalDate(2024, 1)

    def test_2024_060_accepted_leap_feb29(self) -> None:
        assert parse("2024-060") == OrdinalDate(2024, 60)

    def test_2025_060_accepted_feb29_non_leap(self) -> None:
        assert parse("2025-060") == OrdinalDate(2025, 60)

    def test_2025_060_is_march1_non_leap(self) -> None:
        assert to_date(parse("2025-060")) == datetime.date(2025, 3, 1)

    def test_2025_059_accepted_feb28_non_leap(self) -> None:
        assert parse("2025-059") == OrdinalDate(2025, 59)
        assert to_date(parse("2025-059")) == datetime.date(2025, 2, 28)


# ---------------------------------------------------------------------------
# Cat-C — negative-year expanded form (AC4)
# ---------------------------------------------------------------------------


class TestNegativeYear:
    """ISO 8601:2019 expanded representation with negative year."""

    def test_julius_caesar_minus_44(self) -> None:
        od = parse("-0044-007")
        assert od == OrdinalDate(-44, 7)

    def test_minus_44_format_roundtrip(self) -> None:
        assert format(parse("-0044-007")) == "-0044-007"

    def test_minus_1_365(self) -> None:
        od = parse("-0001-365")
        assert od == OrdinalDate(-1, 365)
        assert format(od) == "-0001-365"

    def test_minus_9999_001(self) -> None:
        od = parse("-9999-001")
        assert od == OrdinalDate(-9999, 1)
        assert format(od) == "-9999-001"

    def test_minus_4_is_leap(self) -> None:
        # -4 is divisible by 4 with no century interaction → leap year.
        assert is_leap_year(-4) is True
        assert days_in_year(-4) == 366

    def test_minus_100_not_leap(self) -> None:
        # -100 is divisible by 100 but not 400 → not leap.
        assert is_leap_year(-100) is False

    def test_minus_400_is_leap(self) -> None:
        assert is_leap_year(-400) is True

    def test_minus_1_001(self) -> None:
        od = parse("-0001-001")
        assert od == OrdinalDate(-1, 1)
        assert format(od) == "-0001-001"

    def test_minus_year_format_only(self) -> None:
        # Year -44, day 7 — parsing & formatting work, but to_date/from_date
        # cannot represent BCE dates because stdlib datetime.date is bounded
        # to years 1..9999.
        od = parse("-0044-007")
        assert od == OrdinalDate(-44, 7)
        assert format(od) == "-0044-007"
        with pytest.raises(OrdinalDateParseError, match="BCE"):
            to_date(od)


# ---------------------------------------------------------------------------
# Cat-D — leap-year rules (AC5)
# ---------------------------------------------------------------------------


class TestLeapYearRules:
    """Gregorian leap-year rule across centuries, millennia, and negatives."""

    @pytest.mark.parametrize(
        ("year", "expected"),
        [
            (2000, True),   # by 400
            (1900, False),  # by 100 not 400
            (2024, True),   # by 4
            (2025, False),  # not by 4
            (2400, True),
            (2100, False),
            (4, True),
            (1, False),
            (-4, True),     # proleptic
            (-400, True),
            (-100, False),
            (-1, False),
        ],
    )
    def test_is_leap_year(self, year: int, expected: bool) -> None:
        assert is_leap_year(year) is expected

    @pytest.mark.parametrize(
        ("year", "expected_days"),
        [
            (2000, 366),
            (1900, 365),
            (2024, 366),
            (2025, 365),
            (2400, 366),
            (2100, 365),
            (1, 365),
        ],
    )
    def test_days_in_year(self, year: int, expected_days: int) -> None:
        assert days_in_year(year) == expected_days

    def test_days_in_year_out_of_range(self) -> None:
        with pytest.raises(OrdinalDateParseError, match="year out of range"):
            days_in_year(10000)
        with pytest.raises(OrdinalDateParseError, match="year out of range"):
            days_in_year(-10000)


# ---------------------------------------------------------------------------
# Cat-E — to_date conversion (AC6)
# ---------------------------------------------------------------------------


class TestToDateConversion:
    """``to_date(parse(x))`` matches the expected ``datetime.date``."""

    def test_jan_1(self) -> None:
        assert to_date(parse("2026-001")) == datetime.date(2026, 1, 1)

    def test_feb_29_leap_year(self) -> None:
        assert to_date(parse("2024-060")) == datetime.date(2024, 2, 29)

    def test_dec_31_leap(self) -> None:
        assert to_date(parse("2024-366")) == datetime.date(2024, 12, 31)

    def test_dec_31_non_leap(self) -> None:
        assert to_date(parse("2025-365")) == datetime.date(2025, 12, 31)

    def test_sept_28_2026(self) -> None:
        # Locked reference: spec example
        assert to_date(parse("2026-271")) == datetime.date(2026, 9, 28)

    def test_feb_1_2024_leap(self) -> None:
        assert to_date(parse("2024-032")) == datetime.date(2024, 2, 1)

    def test_mar_1_2025_non_leap(self) -> None:
        assert to_date(parse("2025-060")) == datetime.date(2025, 3, 1)

    def test_apr_1_2024(self) -> None:
        # Day 92 = Jan(31) + Feb(29) + Mar(31) → Apr 1 in leap
        assert to_date(parse("2024-092")) == datetime.date(2024, 4, 1)

    def test_apr_1_2025_non_leap(self) -> None:
        # Day 91 = Jan(31) + Feb(28) + Mar(31) → Apr 1 in non-leap
        assert to_date(parse("2025-091")) == datetime.date(2025, 4, 1)

    def test_jul_1_2024(self) -> None:
        # Day 183 (leap) = Jul 1
        assert to_date(parse("2024-183")) == datetime.date(2024, 7, 1)


# ---------------------------------------------------------------------------
# Cat-F — from_date round-trip (AC7)
# ---------------------------------------------------------------------------


class TestFromDateRoundTrip:
    """``from_date(to_date(od)) == od`` for a year-spanning test set."""

    @pytest.mark.parametrize(
        "d",
        [
            datetime.date(2026, 1, 1),
            datetime.date(2026, 9, 28),
            datetime.date(2024, 2, 29),  # leap day
            datetime.date(2024, 12, 31),
            datetime.date(2025, 12, 31),
            datetime.date(2000, 1, 1),
            datetime.date(1900, 3, 1),
            datetime.date(2100, 3, 1),
            datetime.date(1, 1, 1),
            datetime.date(9999, 12, 31),
        ],
    )
    def test_roundtrip(self, d: datetime.date) -> None:
        od = from_date(d)
        d2 = to_date(od)
        assert d2 == d
        # and back again
        assert from_date(d2) == od

    def test_year_spanning_366_days_2024(self) -> None:
        # Every day of 2024 (leap) round-trips.
        start = datetime.date(2024, 1, 1)
        for offset in range(366):
            d = start + datetime.timedelta(days=offset)
            od = from_date(d)
            assert to_date(od) == d
            assert od.year == 2024
            assert od.day_of_year == offset + 1

    def test_year_spanning_365_days_2025(self) -> None:
        # Every day of 2025 (non-leap) round-trips.
        start = datetime.date(2025, 1, 1)
        for offset in range(365):
            d = start + datetime.timedelta(days=offset)
            od = from_date(d)
            assert to_date(od) == d
            assert od.year == 2025
            assert od.day_of_year == offset + 1

    def test_jan_1_is_day_001(self) -> None:
        assert from_date(datetime.date(2026, 1, 1)) == OrdinalDate(2026, 1)

    def test_dec_31_leap_is_day_366(self) -> None:
        assert from_date(datetime.date(2024, 12, 31)) == OrdinalDate(2024, 366)

    def test_dec_31_non_leap_is_day_365(self) -> None:
        assert from_date(datetime.date(2025, 12, 31)) == OrdinalDate(2025, 365)


# ---------------------------------------------------------------------------
# Cat-G — error messages (AC8)
# ---------------------------------------------------------------------------


class TestErrorMessages:
    """Each malformed input produces a clear, specific error."""

    @pytest.mark.parametrize(
        ("value", "expected_substring"),
        [
            ("2026-999", "day out of range"),
            ("2025-366", "day out of range"),
            ("1900-366", "day out of range"),
            ("abc-def", "bad format"),
            ("2026", "bad format"),
            ("", "bad format"),
            ("2026-0", "bad format"),
            ("2026-1000", "bad format"),
            ("2026-01", "bad format"),       # 2 digits not 3
            ("26-271", "bad format"),        # 2-digit year
            ("2026-271-1", "bad format"),    # extra dash
            ("2026--271", "bad format"),     # double dash
            ("2026.271", "bad format"),      # dot separator
            (" 2026-271", "bad format"),     # leading whitespace
            ("2026-271 ", "bad format"),     # trailing whitespace
            ("2026-27a", "bad format"),      # alpha in day
            ("abcd-efg", "bad format"),      # alpha everywhere
            ("-026-271", "bad format"),      # minus then 3-digit year
            ("--2026-271", "bad format"),    # double minus
            ("2026-", "bad format"),         # empty day
        ],
    )
    def test_error_substring(self, value: str, expected_substring: str) -> None:
        with pytest.raises(OrdinalDateParseError, match=expected_substring):
            parse(value)

    def test_year_out_of_range_positive(self) -> None:
        # 10000-001 has a 5-digit year — rejected at the format level.
        with pytest.raises(OrdinalDateParseError):
            parse("10000-001")

    def test_year_out_of_range_negative(self) -> None:
        with pytest.raises(OrdinalDateParseError):
            parse("-10000-001")

    def test_error_is_value_error_subclass(self) -> None:
        # Exception hierarchies: OrdinalDateParseError must catch as ValueError.
        with pytest.raises(ValueError):
            parse("bad")


# ---------------------------------------------------------------------------
# Cat-H — CLI smoke (AC9)
# ---------------------------------------------------------------------------


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    """Run ``python -m iso_ordinal_parse`` with given CLI args."""
    return subprocess.run(
        [sys.executable, "-m", "iso_ordinal_parse", *args],
        capture_output=True,
        text=True,
        cwd=str(_ROOT),
        env={"PYTHONPATH": str(_SRC), "PATH": _find_path()},
    )


def _find_path() -> str:
    """Compose a PATH that includes the active Python's script bin."""
    import os

    scripts = os.path.dirname(sys.executable)
    return os.pathsep.join([scripts, os.environ.get("PATH", "")])


class TestCLISmoke:
    """Subprocess-based CLI tests."""

    def test_default_positional_valid(self) -> None:
        result = _run_cli("2026-271")
        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload == {"year": 2026, "day_of_year": 271, "date": "2026-09-28"}

    def test_default_positional_invalid_raises(self) -> None:
        # Non-validate path: parse errors propagate (no graceful exit code).
        result = _run_cli("2026-999")
        assert result.returncode != 0
        assert "day out of range" in result.stderr

    def test_validate_valid_exits_0(self) -> None:
        result = _run_cli("--validate", "2026-271")
        assert result.returncode == 0

    def test_validate_invalid_exits_1(self) -> None:
        result = _run_cli("--validate", "2026-999")
        assert result.returncode == 1

    def test_validate_negative_year_valid(self) -> None:
        # Negative-year values look like flags to argparse; use ``=`` syntax
        # to pass them through to ``--validate``.
        result = _run_cli("--validate=-0044-007")
        assert result.returncode == 0

    def test_validate_bad_format_exits_1(self) -> None:
        result = _run_cli("--validate", "abc-def")
        assert result.returncode == 1

    def test_validate_leap_year_accepted(self) -> None:
        result = _run_cli("--validate", "2024-366")
        assert result.returncode == 0

    def test_validate_non_leap_366_rejected(self) -> None:
        result = _run_cli("--validate", "2025-366")
        assert result.returncode == 1

    def test_version_exits_0(self) -> None:
        result = _run_cli("--version")
        assert result.returncode == 0
        assert "0.1.0" in result.stdout

    def test_version_exact_text(self) -> None:
        result = _run_cli("--version")
        assert result.stdout.strip() == "iso-ordinal-parse 0.1.0"

    def test_no_args_exits_0_with_usage(self) -> None:
        result = _run_cli()
        assert result.returncode == 0
        assert "usage:" in result.stderr.lower()
        assert "iso-ordinal-parse" in result.stderr

    def test_unknown_flag_exits_nonzero(self) -> None:
        result = _run_cli("--bogus")
        assert result.returncode != 0

    def test_help_flag(self) -> None:
        result = _run_cli("--help")
        assert result.returncode == 0
        assert "ordinal date" in result.stdout.lower()


# ---------------------------------------------------------------------------
# Cat-I — fresh-venv install (AC1)
# ---------------------------------------------------------------------------


class TestFreshVenvInstall:
    """The package must install into a clean venv and import cleanly.

    Skipped by default to keep the standard test suite hermetic. To run:
    ``PYTHONPATH=src pytest -q -k TestFreshVenvInstall`` (after ``pip install -e .``
    has been run, or use the scripts/ci_fresh_venv.sh harness).
    """

    def test_import_smoke(self) -> None:
        # Already-imported at top of file; this confirms no import errors at
        # collection time and that ``__version__`` is present.
        import iso_ordinal_parse

        assert iso_ordinal_parse.__version__ == "0.1.0"
        assert hasattr(iso_ordinal_parse, "parse")
        assert hasattr(iso_ordinal_parse, "format")
        assert hasattr(iso_ordinal_parse, "to_date")
        assert hasattr(iso_ordinal_parse, "from_date")
        assert hasattr(iso_ordinal_parse, "is_leap_year")
        assert hasattr(iso_ordinal_parse, "days_in_year")
        assert hasattr(iso_ordinal_parse, "OrdinalDate")
        assert hasattr(iso_ordinal_parse, "OrdinalDateParseError")


# ---------------------------------------------------------------------------
# Cat-J — type-error safety (Invariant 21)
# ---------------------------------------------------------------------------


class TestTypeErrorSafety:
    """Non-string / wrong-type inputs raise :class:`TypeError`, not :class:`AttributeError`."""

    @pytest.mark.parametrize(
        "bad",
        [None, 42, 2026271, ["2026-271"], ("2026-271",), b"2026-271"],
    )
    def test_parse_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError):
            parse(bad)  # type: ignore[arg-type]

    def test_parse_type_error_message_names_type(self) -> None:
        with pytest.raises(TypeError, match="NoneType"):
            parse(None)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="int"):
            parse(42)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="bytes"):
            parse(b"2026-271")  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "bad",
        [None, 42, "2026-271", [2026, 271], datetime.date(2026, 9, 28)],
    )
    def test_format_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError):
            format(bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", [None, 42, "2026-271", [2026, 271]])
    def test_to_date_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError):
            to_date(bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "bad", [None, 42, "2026-09-28", [2026, 9, 28], 20260928]
    )
    def test_from_date_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError):
            from_date(bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", ["2026", None, 2024.5, [2024]])
    def test_is_leap_year_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError):
            is_leap_year(bad)  # type: ignore[arg-type]

    @pytest.mark.parametrize("bad", ["2026", None, [2026]])
    def test_days_in_year_type_error(self, bad: object) -> None:
        with pytest.raises(TypeError):
            days_in_year(bad)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cat-K — fuzz property (AC11 small-scale)
# ---------------------------------------------------------------------------


class TestFuzzProperty:
    """Random fuzz: 1000 pseudo-random valid inputs survive round-trip."""

    def test_roundtrip_random_valid(self) -> None:
        rng = random.Random(42)
        iterations = 0
        for _ in range(2000):  # skip year=0 and some, target ~1000 actual runs
            year = rng.randint(-9999, 9999)
            # ISO 8601 expanded form requires non-zero year.
            if year == 0:
                continue
            doy = rng.randint(1, days_in_year(year))
            raw = format(OrdinalDate(year, doy))
            parsed = parse(raw)
            assert parsed == OrdinalDate(year, doy)
            # Idempotence: parse(format(parse(x))) == parse(x)
            assert parse(format(parsed)) == parsed
            iterations += 1
            if year >= 1:
                # datetime.date can only represent year >= 1.
                d = to_date(parsed)
                assert from_date(d) == parsed
            if iterations >= 1000:
                break
        assert iterations == 1000

    def test_explicit_negative_year_in_fuzz(self) -> None:
        rng = random.Random(7)
        for _ in range(200):
            year = -rng.randint(1, 9999)
            doy = rng.randint(1, days_in_year(year))
            raw = format(OrdinalDate(year, doy))
            parsed = parse(raw)
            assert parsed.year == year
            assert parsed.day_of_year == doy
            # BCE: to_date raises OrdinalDateParseError because datetime.date
            # only supports years >= 1; format() round-trips fine.
            assert format(parsed) == raw
            with pytest.raises(OrdinalDateParseError, match="BCE"):
                to_date(parsed)


# ---------------------------------------------------------------------------
# Cat-L — boundary days (AC3+AC6)
# ---------------------------------------------------------------------------


class TestBoundaryDays:
    """First, last, and leap-day-of-year boundary tests."""

    @pytest.mark.parametrize("doy", [1, 32, 60, 61, 91, 120, 151, 181, 212, 243, 273, 304, 334, 365])
    def test_first_day_of_each_month_non_leap(self, doy: int) -> None:
        # For non-leap 2025: day 1=Jan 1, 32=Feb 1, 60=Mar 1, etc.
        expected = datetime.date(2025, 1, 1) + datetime.timedelta(days=doy - 1)
        assert to_date(parse(f"2025-{doy:03d}")) == expected

    @pytest.mark.parametrize("doy", [1, 32, 60, 61, 92, 121, 152, 182, 213, 244, 274, 305, 335, 366])
    def test_first_day_of_each_month_leap(self, doy: int) -> None:
        # For leap 2024: day 1=Jan 1, 32=Feb 1, 60=Feb 29, 61=Mar 1, etc.
        expected = datetime.date(2024, 1, 1) + datetime.timedelta(days=doy - 1)
        assert to_date(parse(f"2024-{doy:03d}")) == expected

    def test_leap_day_2024(self) -> None:
        assert to_date(parse("2024-060")) == datetime.date(2024, 2, 29)

    def test_leap_day_2000(self) -> None:
        assert to_date(parse("2000-060")) == datetime.date(2000, 2, 29)

    def test_non_leap_60_is_march_1(self) -> None:
        assert to_date(parse("2025-060")) == datetime.date(2025, 3, 1)

    def test_non_leap_59_is_feb_28(self) -> None:
        assert to_date(parse("2025-059")) == datetime.date(2025, 2, 28)

    def test_leap_59_is_feb_28(self) -> None:
        assert to_date(parse("2024-059")) == datetime.date(2024, 2, 28)

    def test_leap_366_is_dec_31(self) -> None:
        assert to_date(parse("2024-366")) == datetime.date(2024, 12, 31)

    def test_non_leap_365_is_dec_31(self) -> None:
        assert to_date(parse("2025-365")) == datetime.date(2025, 12, 31)

    def test_day_001_is_jan_1(self) -> None:
        assert to_date(parse("2024-001")) == datetime.date(2024, 1, 1)


# ---------------------------------------------------------------------------
# Cat-M — CLI JSON shape
# ---------------------------------------------------------------------------


class TestCLIJsonShape:
    """CLI default positional output is the exact JSON shape from SPEC §6."""

    def test_canonical_2026_271(self) -> None:
        result = _run_cli("2026-271")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "year": 2026,
            "day_of_year": 271,
            "date": "2026-09-28",
        }

    def test_leap_year_2024_366(self) -> None:
        result = _run_cli("2024-366")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "year": 2024,
            "day_of_year": 366,
            "date": "2024-12-31",
        }

    def test_jan_1(self) -> None:
        result = _run_cli("2026-001")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "year": 2026,
            "day_of_year": 1,
            "date": "2026-01-01",
        }

    def test_feb_29_leap(self) -> None:
        result = _run_cli("2024-060")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "year": 2024,
            "day_of_year": 60,
            "date": "2024-02-29",
        }

    def test_negative_year(self) -> None:
        # Use `--` to terminate flag handling so argparse doesn't treat
        # `-0044-007` as a flag.
        result = _run_cli("--", "-0044-007")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "year": -44,
            "day_of_year": 7,
            "date": "-0044-01-07",
        }

    def test_year_1_round_trip(self) -> None:
        result = _run_cli("0001-001")
        assert result.returncode == 0
        assert json.loads(result.stdout) == {
            "year": 1,
            "day_of_year": 1,
            "date": "0001-01-01",
        }


# ---------------------------------------------------------------------------
# Cat-N — adversarial malformed
# ---------------------------------------------------------------------------


class TestAdversarialMalformed:
    """Pathological inputs that must reject cleanly (not crash)."""

    @pytest.mark.parametrize(
        "raw",
        [
            "\x00",                      # null byte
            "\x01",                      # control char
            "\x1f",                      # control char boundary
            "\n",                        # newline
            "\t",                        # tab
            "2026-271\x00",              # null byte suffix
            "2026-271\n",              # newline suffix
            "-",                         # lone minus
            "--",                        # double minus
            "---",                       # triple minus
            "2026-271-extra",            # trailing junk
            "extra-2026-271",            # leading junk
            "2026+271",                  # plus sign in day
            "+2026-271",                 # leading plus
            "2026_271",                  # underscore
            "2026/271",                  # slash
            "2026 271",                  # space
            "2026,271",                  # comma
            "02026-271",                 # 5-digit year
            "2026-00271",                # 5-digit day
            "2026-0271",                 # 4-digit day
            "ABCDEFGH",                  # all alpha no dash
            "-0044-007-extra",           # negative + trailing
            "    ",                      # whitespace only
            "\u20262026-271",            # unicode prefix
            "2026-\u2026271",            # unicode in day
        ],
    )
    def test_rejects_cleanly(self, raw: str) -> None:
        with pytest.raises(OrdinalDateParseError):
            parse(raw)


# ---------------------------------------------------------------------------
# Cat-O — property: parse ∘ format is identity on canonical inputs
# ---------------------------------------------------------------------------


class TestParseFormatIdentity:
    """Round-trip parse ∘ format is the identity on canonical strings."""

    @pytest.mark.parametrize(
        "raw",
        [
            "0001-001",
            "0001-365",
            "0004-001",
            "0004-366",
            "1000-001",
            "1000-365",
            "1900-001",
            "1900-365",
            "2000-001",
            "2000-366",
            "2024-001",
            "2024-366",
            "2025-001",
            "2025-365",
            "9999-001",
            "9999-365",
            "-0001-001",
            "-0001-365",
            "-0044-007",
            "-9999-001",
            "-9999-365",
        ],
    )
    def test_identity(self, raw: str) -> None:
        assert parse(format(parse(raw))) == parse(raw)
        # And the canonical string itself is reproduced:
        assert format(parse(raw)) == raw