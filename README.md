# iso-ordinal-pure

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/prasad-a-abhishek/iso-ordinal-pure)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#key-features)

> **Zero-dependency ISO 8601 ordinal date (`YYYY-DDD`) parser, serializer, and converter.**

Stop hand-rolling `int(s.split('-')[1])` and `datetime(y,1,1) + timedelta(days=...)` — parse, validate, and round-trip ISO 8601 ordinal dates the spec way.

## Quick Start

```bash
pip install git+https://github.com/prasad-a-abhishek/iso-ordinal-pure.git
```

```python
from iso_ordinal_parse import parse, format, to_date, from_date

od = parse("2026-271")                 # OrdinalDate(year=2026, day_of_year=271)
print(format(od))                       # "2026-271"

d = to_date(od)                         # datetime.date(2026, 9, 28)
print(from_date(d) == od)               # True — round-trip
```

CLI:

```bash
$ python -m iso_ordinal_parse "2026-271"
{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}

$ python -m iso_ordinal_parse --validate "2026-999"; echo $?
1
```

## ⚡ Performance & Benchmarks

Measured on Python 3.11.15 (CPython), Linux aarch64, 10 iterations per workload using `time.perf_counter` and `tracemalloc` peak.

| Workload | iso-ordinal-pure | stdlib `strptime("%Y-%j")` | `isodate.parse_date` |
|----------|-----------------:|---------------------------:|---------------------:|
| parse `"2026-271"` (canonical) | **1.38 µs** | 2.33 µs | 1.20 µs |
| parse `"2024-366"` (leap day) | **0.95 µs** | 1.53 µs | (rejects: not 8601 ordinal) |
| parse `"-0044-007"` (BCE expanded) | **0.98 µs** | ValueError (no support) | ValueError |
| format canonical `2026-271` | **0.43 µs** | n/a (no encoder) | n/a |
| `to_date(od)` conversion | **0.46 µs** | n/a | n/a |
| `from_date(d)` conversion | **0.45 µs** | n/a | n/a |
| `is_leap_year(2024)` | **0.13 µs** | n/a | n/a |
| **Bulk: 1,000 mixed corpus** | **944 µs** | 1,517 µs | n/a |
| **Bulk: 100,000 mixed corpus** | **97,105 µs** | n/a | n/a |
| leap-boundary reject `"2025-366"` | **1.08 µs** | 1.00 µs (silently accepts!) | (rejects) |

**Honest interpretation.** stdlib `strptime("%Y-%j", ...)` is the closest baseline, but it has three structural gaps that iso-ordinal-pure closes: (a) **it accepts day 366 in non-leap years** with no error — `strptime("2025-366", "%Y-%j")` returns `2026-01-01` (off-by-one); (b) it has **no encoder** — `strftime("%Y-%j")` returns the same off-by-one bug; (c) it **rejects ISO 8601 expanded negative years** like `-0044-007`. `isodate` is the closest drop-in but it doesn't handle the ordinal form correctly (returns wrong type). `iso-ordinal-pure` is competitive on happy-path throughput, ~1.6x faster than stdlib on bulk 1K mixed corpus, **strictly correct** on leap-boundary validation, and the only option that supports the canonical negative-year form.

Replicate:

```bash
python3 benchmarks/run_benchmark.py
```

Full table at [`benchmarks/BENCHMARK.md`](benchmarks/BENCHMARK.md).

## Why iso-ordinal-pure?

ISO 8601 defines three calendar-date representations: calendar (`YYYY-MM-DD`), ordinal (`YYYY-DDD`), and week (`YYYY-Www-D`). Ordinal dates appear in:

* **NASA EOSDIS** and **NOAA NCEI** satellite data products
* **Aviation METAR/SPECI/TAF** reports (the `270345Z` syntax is day-of-year 27)
* **Defense / NATO** APP-6 reporting formats
* **Fiscal calendars** where day-of-year is the natural business key
* **Embedded firmware logs** where `YYYY-DDD` saves one byte vs `YYYY-MM-DD`

Python's standard library has gaps for ordinal dates:

* `datetime.date.fromisoformat()` rejects `YYYY-DDD` (only `YYYY-MM-DD` and `YYYYMMDD` as of Python 3.11).
* `datetime.strptime("%Y-%j", ...)` decodes but does not validate against the actual calendar — `strptime("2025-366", "%Y-%j")` silently returns `2026-01-01` instead of raising.
* `strftime("%Y-%j")` produces `YYYY-DDD` but with the same off-by-one bug.
* No round-trip `OrdinalDate` value object.
* No support for ISO 8601:2019 expanded representation (`-YYYY-DDD`) for years before 0001.
* Hand-rolled `int(s.split('-')[1])` is one-off per codebase and skips leap-year validation.

`iso-ordinal-pure` fills these gaps with a focused, zero-dependency library: parses, validates against the actual Gregorian calendar (leap vs non-leap), serializes back to canonical form, converts to/from `datetime.date`, supports negative-year expanded form, and includes a small CLI for shell pipelines.

## Key Features & Complete API

* `parse(value: str) -> OrdinalDate` — accept `YYYY-DDD` and `-YYYY-DDD` (expanded representation). Raises `OrdinalDateParseError` on bad format or day-out-of-range.
* `format(ordinal: OrdinalDate) -> str` — canonical round-trip serializer (`YYYY-DDD` or `-YYYY-DDD`).
* `to_date(ordinal: OrdinalDate) -> datetime.date` — convert to stdlib `date` (year 1..9999).
* `from_date(d: datetime.date) -> OrdinalDate` — convert stdlib `date` to `OrdinalDate`.
* `is_leap_year(year: int) -> bool` — proleptic Gregorian leap-year rule (div by 4, except centuries unless by 400).
* `days_in_year(year: int) -> int` — 365 or 366.
* Strict `OrdinalDateParseError` (subclass of `ValueError`) with descriptive reason strings (`"bad format"`, `"day out of range"`, `"year out of range"`).
* CLI: `python -m iso_ordinal_parse "2026-271"` prints JSON-shaped output `{"year", "day_of_year", "date"}`.
* CLI: `python -m iso_ordinal_parse --validate "..."` exits 0 on valid, 1 on invalid (use `--validate=-0044-007` for negative-year values).
* CLI: `python -m iso_ordinal_parse --version` prints package version.
* Year range: -9999 to 9999 (matches `datetime.date`; for `to_date` only year 1..9999 due to stdlib date bounds).
* Day-of-year range: 001-365 (common year), 001-366 (leap year) — strictly validated against the actual Gregorian calendar.
* Zero runtime dependencies. PEP 561 typed (`py.typed` marker).

### Library example

```python
from iso_ordinal_parse import parse, format, to_date, from_date, is_leap_year, days_in_year

# Canonical
od = parse("2026-271")
print(od.year, od.day_of_year)        # 2026 271

# Leap boundary (the most common correctness bug)
parse("2024-366")                      # OK — leap year
parse("2025-366")                      # raises OrdinalDateParseError("day out of range")

# Expanded negative year (44 BCE day 7)
od = parse("-0044-007")
print(format(od))                      # "-0044-007"

# Round-trip via stdlib date
print(from_date(to_date(od)) == od)    # True

# Calendar helpers
print(is_leap_year(2000))              # True  (by-400)
print(is_leap_year(1900))              # False (by-100 not 400)
print(days_in_year(2024))              # 366
```

### CLI flags

| Invocation | Exit | Output |
|---|---|---|
| `python -m iso_ordinal_parse "2026-271"` | 0 | `{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}` |
| `python -m iso_ordinal_parse --validate "2024-366"` | 0 | (silent) |
| `python -m iso_ordinal_parse --validate "2025-366"` | 1 | (silent) |
| `python -m iso_ordinal_parse --validate=-0044-007` | 0 | (silent) |
| `python -m iso_ordinal_parse --version` | 0 | `iso-ordinal-parse 0.1.0` |
| `python -m iso_ordinal_parse` (no args) | 0 | usage on stderr |
| `python -m iso_ordinal_parse --help` | 0 | argparse help |

### Non-goals

* `YYYY-MM-DD` calendar-date parsing (use `datetime.date.isoformat()` / `fromisoformat`).
* `YYYY-Www-D` ISO week-date parsing (use sibling `iso-weekdate-pure`).
* ISO 8601 durations or intervals (future sibling).
* Timezone handling (ordinal dates are wall-clock).
* BCE/CE Julian-calendar support (ISO 8601 is Gregorian only).

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 iso-ordinal-pure authors.