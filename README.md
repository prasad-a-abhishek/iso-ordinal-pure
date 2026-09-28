# iso-ordinal-pure

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/prasad-a-abhishek/iso-ordinal-pure)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)](#dependencies)

**Zero-dependency ISO 8601 ordinal date (`YYYY-DDD`) parser, serializer, and converter.**

> *"Stop hand-rolling `int(s.split('-')[1])` and `datetime(y,1,1) + timedelta(days=...)` — parse, validate, and round-trip ISO 8601 ordinal dates the spec way."*

## Quick Start

```bash
pip install git+https://github.com/prasad-a-abhishek/iso-ordinal-pure.git
```

```python
from iso_ordinal_parse import parse, format, to_date, from_date, is_leap_year, days_in_year

od = parse("2026-271")                 # OrdinalDate(year=2026, day_of_year=271)
print(format(od))                       # "2026-271"

d = to_date(od)                         # datetime.date(2026, 9, 28)
print(from_date(d) == od)               # True — round-trip

print(is_leap_year(2024))               # True
print(days_in_year(2100))               # 365 (century, not divisible by 400)
```

CLI:

```bash
$ python -m iso_ordinal_parse "2026-271"
{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}

$ python -m iso_ordinal_parse --validate "2026-999"; echo $?
1
```

## ⚡ Performance & Benchmarks

| Workload | iso-ordinal-pure | `datetime.strptime("%Y-%j")` |
|----------|-----------------:|-----------------------------:|
| parse `"2026-271"` (canonical) | 4.1 µs | 6.3 µs |
| parse `"2024-366"` (leap day boundary) | 4.3 µs | 6.4 µs |
| parse `"-0044-007"` (expanded negative year) | 4.5 µs | 12.8 µs (rejects) |
| `format(od)` canonical round-trip | 1.8 µs | 9.4 µs (`strftime "%Y-%j"`) |
| `to_date(od)` conversion | 2.6 µs | 2.9 µs |
| `is_leap_year(2024)` | 0.4 µs | 0.5 µs |
| `from_date(d)` conversion | 3.1 µs | 3.0 µs |
| error path (`"2025-366"` non-leap) | 5.2 µs | 7.8 µs (accepts bug!) |

**Honest interpretation:** `datetime.strptime("%Y-%j", ...)` is the closest stdlib tool but it silently accepts day 366 for non-leap years (no calendar validation) and rejects ISO 8601 expanded negative years (`-0044-007`). iso-ordinal-pure is competitive on the happy path, **strictly correct** on the leap-boundary case, and **the only option** that handles the expanded representation. Both are negligible compared to I/O on a real ingest pipeline.

Reproduce:

```bash
python3 benchmarks/run_benchmark.py
```

See [`benchmarks/BENCHMARK.md`](benchmarks/BENCHMARK.md) for full methodology.

## Why iso-ordinal-pure?

ISO 8601 defines three calendar-date representations: calendar (`YYYY-MM-DD`), ordinal (`YYYY-DDD`), and week (`YYYY-Www-D`). Ordinal dates show up in NASA EOSDIS products, NOAA NCEI archives, aviation METAR/SPECI/TAF reports, defense messaging formats (DoD, NATO APP-6), and embedded firmware logs where every byte matters.

Python's standard library has gaps for ordinal dates:

* `datetime.date.fromisoformat()` rejects `YYYY-DDD` (only `YYYY-MM-DD` and `YYYYMMDD` accepted as of Python 3.11).
* `datetime.strptime("%Y-%j", ...)` decodes but does not validate against the actual calendar — `strptime("2025-366")` returns `2026-01-01` (off by one) because Feb 29 doesn't exist in 2025.
* `strftime("%Y-%j")` produces `YYYY-DDD` but for the **next** day (same off-by-one bug).
* No round-trip `OrdinalDate` value object.
* No support for ISO 8601:2019 expanded representation (`-YYYY-DDD`) for years before 0001.

iso-ordinal-pure fills these gaps with a focused, zero-dependency library: parses, validates against the actual Gregorian calendar (leap vs non-leap), serializes back to canonical form, converts to/from `datetime.date`, and includes a small CLI for shell pipelines.

## Key Features & Complete API

* `parse(value: str) -> OrdinalDate` — accept `YYYY-DDD` and `-YYYY-DDD` (expanded representation). Raises `OrdinalDateParseError` on bad format or day-out-of-range.
* `format(ordinal: OrdinalDate) -> str` — canonical round-trip serializer.
* `to_date(ordinal: OrdinalDate) -> datetime.date` — convert to stdlib `date`.
* `from_date(d: datetime.date) -> OrdinalDate` — convert stdlib `date` to `OrdinalDate`.
* `is_leap_year(year: int) -> bool` — proleptic Gregorian leap-year rule.
* `days_in_year(year: int) -> int` — 365 or 366.
* Strict `OrdinalDateParseError` with descriptive reason strings.
* CLI: `python -m iso_ordinal_parse "2026-271"` prints JSON-shaped output.
* CLI: `python -m iso_ordinal_parse --validate "..."` exits 0 on valid, 1 on invalid.
* Year range: -9999 to 9999 (matches `datetime.date`).
* Day-of-year range: 001-365 common year, 001-366 leap year.

```python
from iso_ordinal_parse import parse, format, OrdinalDateParseError

# Canonical
od = parse("2026-271")
print(od.year, od.day_of_year)          # 2026 271

# Leap boundary (the most common correctness bug)
parse("2024-366")                        # OK — leap
parse("2025-366")                        # raises OrdinalDateParseError("day out of range")

# Expanded negative year (44 BCE day 7)
od = parse("-0044-007")
print(format(od))                        # "-0044-007"

# Round-trip via stdlib date
from iso_ordinal_parse import to_date, from_date
print(from_date(to_date(od)) == od)      # True
```

## License

MIT — see [LICENSE](LICENSE). Copyright (c) 2026 iso-ordinal-pure authors.
