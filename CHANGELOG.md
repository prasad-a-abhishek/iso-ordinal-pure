# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.0 — 2026-09-28

### Added
- Initial release of `iso-ordinal-pure`.
- `parse(value: str) -> OrdinalDate` — accept `YYYY-DDD` and `-YYYY-DDD` expanded representation (ISO 8601:2019 §4.4.2).
- `format(ordinal: OrdinalDate) -> str` — canonical round-trip serializer (`YYYY-DDD` or `-YYYY-DDD`).
- `to_date(ordinal) -> datetime.date` — convert ordinal date to stdlib Gregorian date (year 1..9999; BCE raises `OrdinalDateParseError`).
- `from_date(d: datetime.date) -> OrdinalDate` — convert stdlib date to ordinal date.
- `is_leap_year(year: int) -> bool` — proleptic Gregorian leap-year rule (div by 4, except centuries unless by 400).
- `days_in_year(year: int) -> int` — 365 or 366 depending on leap-year rule.
- Strict `OrdinalDateParseError(ValueError)` with descriptive reason strings (`"bad format"`, `"day out of range"`, `"year out of range"`, `"BCE"`).
- TypeError safety on all public functions for non-string / non-int / non-date inputs (Invariant 21).
- CLI: `python -m iso_ordinal_parse "2026-271"` prints `{"year": 2026, "day_of_year": 271, "date": "2026-09-28"}` JSON to stdout.
- CLI: `python -m iso_ordinal_parse --validate "..."` exits 0/1 on valid/invalid. Use `--validate=-0044-007` for negative-year values.
- CLI: `python -m iso_ordinal_parse --version` prints `iso-ordinal-parse 0.1.0`.
- CLI: `python -m iso_ordinal_parse` (no args) prints usage to stderr (exit 0).
- 233 pytest tests across 14 categories (canonical, leap-boundary, negative-year, leap-rules, to_date, from_date, error-msgs, CLI smoke, fresh-venv import, type-error safety, fuzz property, boundary days, CLI JSON shape, adversarial malformed, parse-format identity).
- Fresh-venv install path verified via `pip install .` into a clean venv (AC1).
- `benchmarks/run_benchmark.py` self-contained 1-click replicability harness comparing against stdlib `strptime("%Y-%j")` and `isodate.parse_date` (Invariant 14).
- `benchmarks/BENCHMARK.md` with measured throughput (Python 3.11.15, `time.perf_counter`, `tracemalloc`).
- 6-section README per Invariant 16 (Title+badges / Quick Start / Performance / Why / Features+API / License).
- Zero runtime dependencies (`dependencies = []` in `pyproject.toml`).
- PEP 561 typed package (`py.typed` marker).
- Secret scan CLEAN across `src/`, `tests/`, `benchmarks/`, `README.md`.