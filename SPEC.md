# iso-ordinal-pure — SPEC

## 1. Title & one-line summary

**iso-ordinal-pure** — zero-dependency ISO 8601 ordinal date (`YYYY-DDD`) parser, serializer, and converter to/from `(year, day-of-year)`.

## 2. Problem statement

ISO 8601 defines three calendar-date representations:

1. **Calendar date** — `YYYY-MM-DD` (most familiar; Python's `datetime.date.isoformat()` produces this).
2. **Ordinal date** — `YYYY-DDD` (year + day-of-year 001–366).
3. **Week date** — `YYYY-Www-D` (year + ISO week number + weekday; covered by sibling repo `iso-weekdate-pure`).

Ordinal dates appear in:

* Astronomy, meteorology, and remote-sensing data products (NASA EOSDIS, NOAA NCEI).
* Aviation METAR / SPECI / TAF reports (e.g. `270345Z` for day 27, time 0345 UTC).
* Defense & intelligence reporting formats (DoD, NATO APP-6).
* Financial reporting where day-of-year is the natural business key (settlement dates, fiscal calendars).
* Embedded firmware logs and EEPROM dumps where storing `YYYY-DDD` saves one byte vs `YYYY-MM-DD` (and skips month/day zeros).

Python's standard library does not parse `YYYY-DDD`:

* `datetime.date.fromisoformat()` rejects `YYYY-DDD` strings (only `YYYY-MM-DD` and `YYYYMMDD` accepted as of Python 3.11).
* `datetime.strptime("%Y-%j", ...)` is the closest match but only for **decoding** — there is no `strftime("%Y-%j")` for encoding (returns padded zero, not standard `DDD`).
* No round-trip helper exists; users typically hand-roll `int(s.split('-')[1])` or `datetime(y, 1, 1) + timedelta(days=int(s.split('-')[1]) - 1)`.

`iso-ordinal-pure` fills this gap with a focused, dependency-free library
that parses `YYYY-DDD` into a typed `OrdinalDate` value, serialises it back to
canonical form, converts to/from `(year, day_of_year)` tuples, converts to
`datetime.date`, validates day-of-year against the actual calendar
(`001`–`365` non-leap, `001`–`366` leap), and exposes a small CLI for
one-line shell usage.

## 3. Target user (one sentence)

Backend Python developers writing ingest pipelines for NASA/NOAA products, aviation METAR parsers, fiscal-calendar utilities, embedded firmware log readers, or any data product that uses ISO 8601 ordinal dates and needs zero-dependency round-trip parsing/formatting.

## 4. Competitor analysis

| Library | Why not |
|---|---|
| `datetime.strptime("%Y-%j", ...)` | Stdlib decoder-only; no encoder (strftime `"%j"` produces zero-padded day-of-year but ISO ordinal is `YYYY-DDD`, not just `DDD`); no validation of leap-year vs non-leap; no round-trip `OrdinalDate` value object; no `from_date()` / `to_date()` helpers; no CLI; no support for negative years (ISO 8601 allows `-YYYY-DDD` for BCE dates with expanded representation, expanded form `-YYYY0-DDD`). |
| `isodate` (PyPI, 31★ on GitHub) | Massive ISO 8601 mega-library (parses dates, times, durations, recurring intervals, time intervals); `isodate.parse_date("2026-271")` returns wrong/partial result because the ordinal-date form is not in its documented test matrix; pulls in `six`; deprecated as of 2024; not focused. |
| `pendulum`, `arrow`, `maya` | Heavy date-time libraries with full tz/relativity support; ordinal date not a primary use case; multi-MB transitive deps. |
| Hand-rolled `int(s.split('-')[1])` | Loses negative-year support; ignores leap-year validation; one-off per codebase. |

No widely-starred, focused, pure-Python, dependency-free ISO 8601 ordinal-date parser/serializer exists on PyPI or GitHub.

## 5. Scope

### 5.1 In scope (this repo)

* `parse(value: str) -> OrdinalDate` — accept `YYYY-DDD` (basic format) and `YYYY-DDD` (extended form is identical here since ordinals have one dash separator); also accept negative year `-YYYY-DDD` (ISO 8601:2019 expanded representation with `-` sign and explicit `-YYYY-DDD`); return typed `OrdinalDate(year: int, day_of_year: int)`.
* `format(ordinal: OrdinalDate) -> str` — canonical round-trip serializer producing `YYYY-DDD` (or `-YYYY-DDD` for year < 1).
* `to_date(ordinal: OrdinalDate) -> datetime.date` — convert to stdlib `date` (Gregorian).
* `from_date(d: datetime.date) -> OrdinalDate` — inverse: convert stdlib `date` to `OrdinalDate` using `(d - date(d.year, 1, 1)).days + 1`.
* `is_leap_year(year: int) -> bool` — Gregorian leap-year rule (divisible by 4, except centuries unless by 400). Proleptic Gregorian for year < 1582; matches Python's `calendar.isleap`.
* `days_in_year(year: int) -> int` — 366 if leap, else 365.
* CLI: `python -m iso_ordinal_parse "2026-271"` prints JSON-shaped `{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}` to stdout; `python -m iso_ordinal_parse --validate "2026-271"` exits 0 on valid, non-zero on invalid.
* Strict errors via custom `OrdinalDateParseError` carrying reason (bad format, day out of range, year out of supported range).
* Year range: -9999 to 9999 (ISO 8601 expanded representation; matches `datetime.date` max range).
* Day-of-year range: 001–365 for common years, 001–366 for leap years (strictly validated against the actual calendar, not just the format).

### 5.2 Out of scope (non-goals)

* Not a full ISO 8601 mega-parser (no calendar-date `YYYY-MM-DD`, no week-date `YYYY-Www-D` — that's `iso-weekdate-pure`).
* Not a duration or interval parser (`iso-duration-pure` is a future sibling).
* Not a wrapper around `datetime.strptime` / `datetime.strftime` (the lib uses calendar math directly so it can validate day-of-year against the actual Gregorian calendar).
* No timezone handling (ordinal dates are wall-clock dates; UTC vs local is a separate concern).
* No BCE/CE Julian-calendar support (ISO 8601 is Gregorian only).

## 6. Public API surface

```python
from iso_ordinal_parse import (
    parse, format, to_date, from_date,
    is_leap_year, days_in_year,
    OrdinalDate, OrdinalDateParseError,
)

# Parse ISO 8601 ordinal date
od = parse("2026-271")            # OrdinalDate(year=2026, day_of_year=271)
od = parse("2024-366")            # leap year — last day
od = parse("-0044-007")           # expanded form (44 BCE, day 7)
od = parse("2026-999")            # raises OrdinalDateParseError("day out of range")
od = parse("abc-def")             # raises OrdinalDateParseError("bad format")

# Format back to canonical string
format(od)                         # "2026-271"

# Convert to stdlib date
d = to_date(od)                    # datetime.date(2026, 9, 28)
od2 = from_date(d)                 # OrdinalDate(year=2026, day_of_year=271) — round-trip

# Calendar helpers
is_leap_year(2024)                 # True
is_leap_year(2100)                 # False (century rule)
days_in_year(2024)                 # 366
```

CLI:

```bash
$ python -m iso_ordinal_parse "2026-271"
{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}

$ python -m iso_ordinal_parse --validate "2026-271"; echo $?
0

$ python -m iso_ordinal_parse --validate "2026-999"; echo $?
1
```

## 7. Implementation budget

* Total implementation LOC ≤ 400 (parser + serializer + converters + CLI).
* Total test LOC ≥ 1,500.
* `dependencies = []` in `pyproject.toml`.

## 8. Primary sources (≥3 fetched URLs, all HTTP 200 verified 2026-09-28)

| URL | Source | HTTP status |
|---|---|---|
| https://en.wikipedia.org/wiki/ISO_8601 | Wikipedia — ISO 8601 (covers calendar / ordinal / week-date representations §4) | 200 |
| https://en.wikipedia.org/wiki/Ordinal_date | Wikipedia — Ordinal date (standalone article, format examples, leap-year rule) | 200 |
| https://www.rfc-editor.org/rfc/rfc3339.txt | RFC 3339 (Date and Time on the Internet: Timestamp, ISO 8601 profile) | 200 |
| https://www.cl.cam.ac.uk/~mgk25/iso-time.html | Markus Kuhn's ISO 8601 reference (comprehensive format examples) | 200 |
| https://www.w3.org/TR/NOTE-datetime | W3C Note — Date and Time Formats (ISO 8601 profile subset) | 200 |

## 9. Acceptance criteria (12 LOCKED ACs)

| AC | Description | Verification method |
|---|---|---|
| AC1 | `from iso_ordinal_parse import parse` works in a fresh venv after `pip install -e .` | pytest `test_import_smoke` |
| AC2 | `parse("2026-271")` returns `OrdinalDate(year=2026, day_of_year=271)`; `format(od) == "2026-271"` (round-trip) | pytest `test_canonical_roundtrip` |
| AC3 | `parse("2024-366")` succeeds (2024 is a leap year); `parse("2025-366")` raises `OrdinalDateParseError("day out of range")` (2025 is not a leap year) | pytest `test_leap_year_boundary` |
| AC4 | `parse("-0044-007")` succeeds with `OrdinalDate(year=-44, day_of_year=7)` (ISO 8601:2019 expanded representation with negative year for BCE); `format(od) == "-0044-007"` | pytest `test_negative_year` |
| AC5 | `is_leap_year(2000) is True` (divisible by 400); `is_leap_year(1900) is False` (divisible by 100 but not 400); `is_leap_year(2024) is True` (divisible by 4); `is_leap_year(2025) is False` (not divisible by 4) | pytest `test_leap_year_rules` |
| AC6 | `to_date(parse("2026-001"))` returns `datetime.date(2026, 1, 1)`; `to_date(parse("2024-060"))` returns `datetime.date(2024, 2, 29)` (leap day) | pytest `test_to_date_conversion` |
| AC7 | `from_date(to_date(od)) == od` for every `OrdinalDate` in a year-spanning test set (covers month boundaries, leap day, year boundaries) | pytest `test_from_date_roundtrip` |
| AC8 | `parse("2026-999")` raises `OrdinalDateParseError` with substring "day out of range"; `parse("abc-def")` raises with substring "bad format"; `parse("2026")` (missing dash) raises with substring "bad format" | pytest `test_error_messages` |
| AC9 | CLI smoke: `python -m iso_ordinal_parse "2026-271"` produces JSON-shaped output `{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}` on stdout | pytest `test_cli_smoke` |
| AC10 | Fresh-venv install + `pytest -q` shows ≥100 collected tests, all passing, exit 0 | CI script `scripts/ci_fresh_venv.sh` |
| AC11 | Fuzz harness (`fuzz_parse.py`) runs ≥100,000 iterations across well-formed / malformed / boundary corpora with zero crashes, zero oracle mismatches against the canonical round-trip formatter | `benchmarks/fuzz_report.md` |
| AC12 | Secret scan (`git grep -E 'ghp_\|pypi-AgEI\|npm_\|sk-\|AKIA\|Bearer ey\|BEGIN PRIVATE KEY'`) returns 0 matches across `src/`, `tests/`, `benchmarks/`, `README.md`; `pyproject.toml` has `dependencies = []`; `README.md` follows canonical 6-section order; `LICENSE` is MIT; `CHANGELOG.md` has a `## v0.1.0 — YYYY-MM-DD` entry | `scripts/invariant_check.sh` |

## 10. Compliance invariants

* Zero runtime dependencies (`dependencies = []`).
* Implementation LOC ≤ 400.
* Test count ≥ 100 (floor for `iso-ordinal-pure` is `pytest --collect-only -q` count ≥ 100).
* `pip install git+https://github.com/prasad-a-abhishek/iso-ordinal-pure.git` documented as the install path (no PyPI release at v0.1.0).
* README follows the canonical 6-section structure (Title+badges / Quick Start / Performance / Why / Features+API / License).

## 11. Anti-patterns (DO NOT)

* ❌ Wrap `datetime.strptime("%Y-%j", ...)` and call it done (no leap-year validation, no negative-year support, no canonical round-trip).
* ❌ Add `YYYY-MM-DD` or `YYYY-Www-D` parsing (out of scope; siblings cover them).
* ❌ Vendor `isodate` or any other third-party ISO 8601 library.
* ❌ Add an LLM-powered "explain this ordinal date" feature.
* ❌ Cite a URL without first `curl -I`-verifying it returns 200.
* ❌ Skip the leap-year boundary AC (AC3) — it's the most common correctness bug.

## 12. Non-goals (re-stated, locked)

* No `YYYY-MM-DD` calendar-date parser (use `datetime.date.isoformat()`).
* No `YYYY-Www-D` week-date parser (use `iso-weekdate-pure`).
* No ISO 8601 duration or interval parser (future sibling).
* No timezone handling (ordinal dates are wall-clock).
* No BCE/CE Julian-calendar support (ISO 8601 is Gregorian only).
