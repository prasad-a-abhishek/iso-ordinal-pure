# Surfaces — iso-ordinal-pure

**Repo:** iso-ordinal-pure (ISO 8601:2019 §4.4.2 ordinal date `YYYY-DDD`)
**Cycle:** 137 / T1 (manual vulnerability audit)
**Methodology:** Enumerate every public entry point (Python API + CLI + module
surface) and identify the attack surface, validation, and tests covering it.

**Source commit audited:** 57a8cab (cycle_137/qa VERDICT:SHIP)

---

## 1. Module surface (`import iso_ordinal_parse`)

`src/iso_ordinal_parse/__init__.py` re-exports from
`iso_ordinal_parse._iso_ordinal_parse` and pins the version.

| Symbol | Kind | Source line | Audit notes |
|---|---|---|---|
| `__version__` | `str` constant `"0.1.0"` | __init__.py:21 | Static, not attacker-controlled. |
| `OrdinalDate` | `NamedTuple(year: int, day_of_year: int)` | _iso_ordinal_parse.py:61-71 | Frozen typed value. Constructor not exposed — instances are returned by `parse()` / `from_date()` only. |
| `OrdinalDateParseError` | `ValueError` subclass | _iso_ordinal_parse.py:74-81 | Exception type. The expected error class for all parse failures. |
| `parse(value: str)` | public function | _iso_ordinal_parse.py:143-202 | **Primary attack surface.** Validates str type, format, ranges. |
| `format(ordinal: OrdinalDate)` | public function | _iso_ordinal_parse.py:210-230 | Validates OrdinalDate type. Pure compute. |
| `to_date(ordinal: OrdinalDate)` | public function | _iso_ordinal_parse.py:238-279 | Validates OrdinalDate type. Rejects year<1 (BCE). |
| `from_date(d: datetime.date)` | public function | _iso_ordinal_parse.py:282-295 | Validates datetime.date type. |
| `is_leap_year(year: int)` | public function | _iso_ordinal_parse.py:89-110 | Validates int (NOT bool). |
| `days_in_year(year: int)` | public function | _iso_ordinal_parse.py:113-128 | Validates int (NOT bool). Year-range-checked. |

`__all__` (line 23-33 of __init__.py) explicitly enumerates the public surface.
No name is in `__all__` that is not actually exported.

---

## 2. CLI surface (`python -m iso_ordinal_parse` and `iso-ordinal-pure`)

`src/iso_ordinal_parse/__main__.py` defines `main(argv)` + `_build_parser()`.

### 2.1 Console-script binary

Per `pyproject.toml [project.scripts]`:
```
iso-ordinal-pure = "iso_ordinal_parse.__main__:main"
```

After `pip install -e .`, `iso-ordinal-pure` is on `$PATH`. NOTE: the binary
name (`iso-ordinal-pure`) differs from the program name displayed by `--help`
and `--version` (`iso-ordinal-parse`). This is cosmetic, not a security issue.
See TEST_GAPS.md §3.

### 2.2 argparse arguments

| Arg | Type | Behavior |
|---|---|---|
| `value` | positional, optional | The ordinal date string. If absent AND `--validate` absent, prints usage to stderr, exit 0. |
| `--validate VALUE` | optional flag | Validate only. Exit 0 if valid, 1 if `OrdinalDateParseError`. |
| `--version` | `store_true` flag | Print `"iso-ordinal-parse <version>"` to stdout, exit 0. |
| `-h`, `--help` | built-in | Standard argparse help. |
| anything else | unknown | argparse exits 2 with usage on stderr. |

### 2.3 CLI modes

| Invocation | Input flow | Output flow | Exit codes |
|---|---|---|---|
| `main([])` | none | usage to stderr | 0 |
| `main(["2026-271"])` | parse → JSON | `{year, day_of_year, date}` to stdout | 0 |
| `main(["2026-999"])` | parse → OrdinalDateParseError | re-raise (caller sees traceback) | non-zero (uncaught) |
| `main(["--validate", "2026-271"])` | parse → silent success | none | 0 |
| `main(["--validate", "2026-999"])` | parse → OrdinalDateParseError | suppressed | 1 |
| `main(["--version"])` | none | `"iso-ordinal-parse 0.1.0"` to stdout | 0 |
| `main(["--help"])` | none | argparse help to stdout | 0 |
| `main(["--bogus"])` | argparse rejects | argparse usage to stderr | 2 (argparse default) |

**Security observations:**

1. **No shell exec.** `argparse` stores argv as a `list[str]`; `main()` only
   reads `args.value` / `args.validate` and passes them to `parse()`. No
   `subprocess.*`, no `os.system`, no `eval`, no `exec`.
2. **JSON output is type-safe.** `json.dumps(payload, separators=(", ", ": "))`
   serializes only `int` and `str` fields; no user-controlled dict keys or
   values can inject JSON-escape sequences (they go through json.dumps'
   built-in escaping).
3. **`--validate` cleanly returns 1 on parse error.** The non-validate path
   re-raises (so callers see the error), matching the documented SPEC behavior.
4. **BCE year in positional arg requires `--` separator** (argparse interprets
   `-0044-007` as a flag). Documented in CLI `--help` and the `_USAGE` text
   on the no-args path.

---

## 3. Public Python API — input/output type contracts

| Function | Input type | Output type | Raises |
|---|---|---|---|
| `parse(value: str)` | `str` | `OrdinalDate` | `TypeError` on non-str; `OrdinalDateParseError` on bad format / OOR day / OOR year |
| `format(ordinal: OrdinalDate)` | `OrdinalDate` | `str` | `TypeError` on non-OrdinalDate |
| `to_date(ordinal: OrdinalDate)` | `OrdinalDate` | `datetime.date` | `TypeError` on non-OrdinalDate; `OrdinalDateParseError` on year<1 |
| `from_date(d: datetime.date)` | `datetime.date` | `OrdinalDate` | `TypeError` on non-datetime.date |
| `is_leap_year(year: int)` | `int` (not bool) | `bool` | `TypeError` on non-int |
| `days_in_year(year: int)` | `int` (not bool) | `int` | `TypeError` on non-int; `OrdinalDateParseError` on year OOR |

All exception contracts verified live (see THREAT_MODEL.md §4).

---

## 4. Files audited

| Path | LOC | Role |
|---|---|---|
| `src/iso_ordinal_parse/__init__.py` | 32 | Re-exports public API, pins version. |
| `src/iso_ordinal_parse/_iso_ordinal_parse.py` | 295 | Reference implementation: types, parser, serializer, converters, calendar helpers. |
| `src/iso_ordinal_parse/__main__.py` | 133 | CLI entrypoint (argparse + JSON output). |
| `src/iso_ordinal_parse/py.typed` | 0 | PEP 561 marker. |
| **Total** | **460** | Within SPEC §7 budget of ≤1000 LOC. |

---

## 5. Test coverage of surfaces

| Surface | Existing tests | Coverage assessment |
|---|---|---|
| `parse` happy paths | TestParseFormatIdentity, TestLeapYearBoundary, TestNegativeYear (Cat-A/B/C) | Strong. 233 corpus entries. |
| `parse` errors | TestErrorMessages (Cat-G) | Strong. 21 parametrized error substrings. |
| `parse` type errors | TestTypeErrorSafety.test_parse_type_error (6 cases) | Adequate. Covers None, int, list, dict, bytes, tuple. |
| `format` happy paths | TestParseFormatIdentity round-trip | Strong. 233 entries. |
| `format` type errors | TestTypeErrorSafety.test_format_type_error | Adequate. |
| `to_date` happy paths | TestToDate (Cat-D, 10+ cases) | Strong. Covers leap-year boundaries. |
| `to_date` BCE/year<1 rejection | **None** | **Gap.** See TEST_GAPS.md §1. |
| `to_date` type errors | TestTypeErrorSafety.test_to_date_type_error | Adequate. |
| `from_date` happy paths | TestFromDate (Cat-E, 4 cases + round-trip in TestFromDateRoundTrip) | Strong. |
| `from_date` type errors | TestTypeErrorSafety.test_from_date_type_error (5 cases) | Strong. |
| `is_leap_year` happy paths | TestIsLeapYear parametrization (Cat-F) | Strong. |
| `is_leap_year` bool/float/str rejection | **None** (TestTypeErrorSafety covers general type errors but doesn't explicitly parametrize bool/float/str) | **Gap.** See TEST_GAPS.md §1. |
| `days_in_year` happy paths | TestDaysInYear | Adequate. |
| `days_in_year` OOR year | TestDaysInYearOutOfRange | Adequate. |
| `days_in_year` type errors | TestTypeErrorSafety.test_days_in_year_type_error | Adequate. |
| CLI smoke | TestCLISmoke (Cat-H, 12 cases) | Strong. Covers valid/invalid/version/help/no-args/unknown-flag/BCE-via-=. |
| CLI shell-meta / Unicode digits / 1MB argv | **None** | **Gap.** See TEST_GAPS.md §2. |

---

## 6. Surfaces NOT present (negative enumeration)

To prevent future audits from re-investigating, these surfaces are explicitly
NOT part of this codebase:

- No HTTP server / client.
- No file I/O (`open`, `pathlib`, `os.path`).
- No database driver.
- No subprocess invocation.
- No environment variable reads (other than `PATH` inside the CLI test harness).
- No thread / process / async primitives.
- No socket / network code.
- No serialization formats other than JSON (used only in CLI output).
- No timezone handling (out of scope per SPEC §5.2; ordinal dates are wall-clock).
- No regex (verified by `grep -nE "re\.|regex" src/iso_ordinal_parse/*.py` → 0 hits).

---

VERDICT: CLEAN (all enumerated surfaces audited; gaps identified for T2/T3
to close, but no exploitable finding)