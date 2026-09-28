# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.1.0 — 2026-09-28

### Added
- Initial release of `iso-ordinal-pure`.
- `parse(value: str) -> OrdinalDate` — accept `YYYY-DDD` and `-YYYY-DDD` expanded representation.
- `format(ordinal: OrdinalDate) -> str` — canonical round-trip serializer.
- `to_date(ordinal) -> datetime.date` — convert ordinal date to stdlib Gregorian date.
- `from_date(d: datetime.date) -> OrdinalDate` — convert stdlib date to ordinal date.
- `is_leap_year(year: int) -> bool` — proleptic Gregorian leap-year rule.
- `days_in_year(year: int) -> int` — 365 or 366 depending on leap-year rule.
- Strict `OrdinalDateParseError` with descriptive reason strings.
- CLI: `python -m iso_ordinal_parse "2026-271"` prints JSON-shaped output.
- CLI: `python -m iso_ordinal_parse --validate "2026-271"` exits 0/1 on valid/invalid.
- ≥100 pytest tests covering canonical, leap-boundary, negative-year, error-message, CLI, round-trip, and from-date scenarios.
- Fuzz harness covering well-formed, malformed, and boundary inputs.
