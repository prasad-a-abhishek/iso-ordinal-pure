# Vulnerability Audit — iso-ordinal-pure

**Repo:** iso-ordinal-pure (ISO 8601:2019 §4.4.2 ordinal date `YYYY-DDD`)
**Cycle:** 137 / T1 (manual vulnerability audit, per Invariant 26 §1)
**Auditor profile:** default (cycle_124 #842 — repo-adversary stopped, default inherits)
**Audit date:** 2026-09-28
**Commit audited:** 57a8cab (cycle_137/qa VERDICT:SHIP, 233/233 pytest)
**Worktree:** /root/projects/iso-ordinal-pure/.worktrees/t_cycle137-adv-01

---

## Executive summary

The audit exercised **every public API function** (parse, format, to_date,
from_date, is_leap_year, days_in_year) **and every CLI mode** (positional,
--validate, --version, --help, no-args, unknown flag) against **70+
adversarial inputs** spanning the threat-model vectors. No exploitable
vulnerability was found. No uncaught exception, no crash, no hang, no OOM,
no silent mis-parse, no shell-injection vector, no OOB read, no integer
overflow (Python ints are unbounded but `parse()` rejects oversized year
BEFORE int conversion).

The implementation has **defense-in-depth validation**: every public function
explicit-checks input types (`isinstance`) and value ranges, raising clean
`TypeError` / `OrdinalDateParseError`. The CLI uses `argparse` (no shell
exec). The package has `dependencies = []` (no supply-chain risk from third
parties). All tests pass (233/233).

---

## Methodology

1. **Read all source code** — `src/iso_ordinal_parse/__init__.py` (32 LOC),
   `_iso_ordinal_parse.py` (295 LOC), `__main__.py` (133 LOC). 460 LOC total
   within the SPEC §7 budget (≤1000).

2. **Read the test suite** — 87 `def test_*` + 146 parametrizations = 233 tests.
   Identified which threat-model vectors are covered and which are gaps
   (see `TEST_GAPS.md`).

3. **Live-probed every threat-model vector** — Wrote a probe script
   (`/tmp/audit_probes.py`, 100 lines) that invokes each public function
   with each adversarial input and classifies the result. Every probe
   returned a clean error or expected success (no uncaught exception).

4. **Live-probed the CLI** — Used `subprocess` (via `iso_ordinal_parse.__main__.main(argv)`)
   with each CLI invocation pattern, including shell-metachar inputs and
   1MB argv.

5. **Confirmed the 233-test suite passes** — `pytest -q` → `233 passed in 0.46s`.

6. **Enumerated applicable CWEs** — See `CWE_MAP.md`. 3 of 20 candidate CWEs
   apply (CWE-20 input validation, CWE-704 type conversion, CWE-400 resource
   consumption); all are mitigated by the implementation.

7. **Documented gaps** — See `TEST_GAPS.md`. 9 defense-in-depth improvements
   identified for T2/T3; none exploitable.

---

## Findings

### Findings by severity

| Severity | Count | IDs |
|---|---|---|
| Critical | **0** | — |
| High | **0** | — |
| Medium | **0** | — |
| Low | **0** | — |
| Info | 0 | — |
| **Total** | **0** | — |

**No findings.** No exploitable vulnerability, no advisory, no
recommendation for code change required before ship.

### Findings by CWE

| CWE | Title | Status |
|---|---|---|
| CWE-20 | Improper Input Validation | Mitigated (5-gate validation in `parse()`) |
| CWE-400 | Uncontrolled Resource Consumption | Mitigated (O(n) parsing, no regex) |
| CWE-704 | Incorrect Type Conversion | Mitigated (explicit `isinstance` on every public function) |

All other 17 CWEs in the candidate list do not apply to this codebase by
construction (no I/O, no C extension, no dynamic dispatch, no regex, no auth).
See `CWE_MAP.md` for full analysis.

---

## Live-probe evidence (excerpt from `/tmp/audit_probes.py`)

| # | Probe | Result |
|---|---|---|
| 1 | `parse("2024-99999")` | `OrdinalDateParseError: bad format: day part '99999' must be exactly 3 digits` |
| 2 | `parse("2024-999999999")` | `OrdinalDateParseError` (length gate) |
| 3 | `parse("2024--5")` | `OrdinalDateParseError: bad format: expected YYYY-DDD` |
| 4 | `parse("2024-0")` | `OrdinalDateParseError: bad format: day part '0' must be exactly 3 digits` |
| 5 | `parse("-0044-060")` (AC4) | `OrdinalDate(year=-44, day_of_year=60)` ✓ |
| 6 | `parse("0000-001")` | `OrdinalDate(year=0, day_of_year=1)` ✓ |
| 7 | `parse("-0000-060")` | `OrdinalDate(year=0, day_of_year=60)` ✓ (sign × 0 = 0) |
| 8 | `parse(None)` | `TypeError: parse() expected str, got NoneType` ✓ |
| 9 | `parse([])` | `TypeError: parse() expected str, got list` ✓ |
| 10 | `parse(b"2024-060")` | `TypeError: parse() expected str, got bytes` ✓ |
| 11 | `parse("")` | `OrdinalDateParseError: bad format: expected YYYY-DDD, got ''` ✓ |
| 12 | `parse("   ")` | `OrdinalDateParseError: bad format` ✓ |
| 13 | `parse("\t")`, `parse("\n")` | `OrdinalDateParseError` ✓ |
| 14 | `parse("2024\x00-060")` | `OrdinalDateParseError: year part '2024\x00' must be exactly 4 digits` ✓ |
| 15 | `parse("\u0662\u0660\u0662\u0664-\u0660\u0666\u0660")` (Arabic-Indic) | `OrdinalDateParseError` ✓ |
| 16 | `parse("\uFF12\uFF10\uFF12\uFF14-\uFF10\uFF16\uFF10")` (Fullwidth) | `OrdinalDateParseError` ✓ |
| 17 | `parse("2024- 060")` (internal ws) | `OrdinalDateParseError` ✓ |
| 18 | `parse(" 2024-060")` (leading ws) | `OrdinalDateParseError` ✓ |
| 19 | `parse("2024-060 ")` (trailing ws) | `OrdinalDateParseError` ✓ |
| 20 | `parse("2024--060")` (double dash) | `OrdinalDateParseError` ✓ |
| 21 | `parse("--2024-060")` (double minus) | `OrdinalDateParseError` ✓ |
| 22 | `parse("9999999999-060")` (10-digit year) | `OrdinalDateParseError: year part length ≠ 4` ✓ |
| 23 | `parse("99999999999999999999999-060")` (huge year) | `OrdinalDateParseError: year part length ≠ 4` (rejected BEFORE int parse) ✓ |
| 24 | `parse("1900-366")` (century non-leap) | `OrdinalDateParseError: day out of range` ✓ |
| 25 | `parse("2000-366")` (century by 400) | `OrdinalDate(year=2000, day_of_year=366)` ✓ |
| 26 | `parse("2024-366")` (regular leap) | `OrdinalDate(year=2024, day_of_year=366)` ✓ |
| 27 | `parse("2100-366")` (future century non-leap) | `OrdinalDateParseError` ✓ |
| 28 | `format(None)` | `TypeError: format() expected OrdinalDate, got NoneType` ✓ |
| 29 | `format("2024-60")` | `TypeError: format() expected OrdinalDate, got str` ✓ |
| 30 | `format(OrdinalDate(-44, 7))` | `"-0044-007"` ✓ |
| 31 | `format(OrdinalDate(0, 1))` | `"0000-001"` ✓ |
| 32 | `to_date(parse("0000-001"))` (year=0) | `OrdinalDateParseError: cannot convert BCE year 0: datetime.date only supports years 1..9999` ✓ |
| 33 | `to_date(parse("-0044-060"))` (BCE) | `OrdinalDateParseError: cannot convert BCE year -44` ✓ |
| 34 | `to_date(None)` | `TypeError` ✓ |
| 35 | `from_date(None)` | `TypeError` ✓ |
| 36 | `from_date("2024-01-01")` | `TypeError` ✓ |
| 37 | `from_date([2024, 1, 1])` | `TypeError` ✓ |
| 38 | `is_leap_year(True)` | `TypeError: is_leap_year() expected int, got bool` ✓ (explicit bool-rejection) |
| 39 | `is_leap_year(1.0)` | `TypeError: is_leap_year() expected int, got float` ✓ |
| 40 | `is_leap_year("2024")` | `TypeError: is_leap_year() expected int, got str` ✓ |
| 41 | `is_leap_year(None)` | `TypeError` ✓ |
| 42 | `is_leap_year(10**100)` | `True` (O(1) modulo, no OOM) ✓ |
| 43 | `is_leap_year(10**1000)` | `True` ✓ |
| 44 | `days_in_year(10000)` | `OrdinalDateParseError: year out of range` ✓ |
| 45 | `days_in_year(10**100)` | `OrdinalDateParseError: year out of range` (no allocation) ✓ |
| 46 | `main(["2026-271"])` | exit 0, JSON `{year:2026, day_of_year:271, date:"2026-09-28"}` ✓ |
| 47 | `main(["--validate", "2026-999"])` | exit 1 ✓ |
| 48 | `main(["--validate=-0044-007"])` (BCE) | exit 0 ✓ |
| 49 | `main(["--validate=-9999-366"])` (BCE OOR) | exit 1 ✓ |
| 50 | `main(["--validate", "; rm -rf /"])` (shell meta) | exit 1, `OrdinalDateParseError`, no exec ✓ |
| 51 | `main(["--validate", "\u0662\u0660\u0662\u0664-\u0660\u0666\u0660"])` (Arabic-Indic) | exit 1 ✓ |
| 52 | `main(["--bogus"])` (unknown flag) | argparse exits 2 (standard non-zero) ✓ |
| 53 | `main(["--validate", "A"*1_000_000])` (1MB argv) | exit 1 in <100ms, no crash, no hang ✓ |
| 54 | `main([])` (no args) | exit 0, usage on stderr ✓ |
| 55 | `main(["--version"])` | exit 0, `"iso-ordinal-parse 0.1.0"` ✓ |
| 56 | `main(["--help"])` | exit 0, argparse help ✓ |
| 57 | round-trip `format(parse(x))==x` for 6 boundary cases | all PASS ✓ |
| 58 | `to_date(parse("2024-366"))` | `datetime.date(2024, 12, 31)` ✓ |
| 59 | `to_date(parse("2024-060"))` | `datetime.date(2024, 2, 29)` ✓ |
| 60 | `to_date(parse("9999-365"))` (year max boundary) | `datetime.date(9999, 12, 31)` ✓ |

Full transcript: see `/tmp/audit_probes.py` and its captured stdout
(captured during this audit, 2026-09-28).

---

## Defense-in-depth observations (NOT findings)

These are positive observations of the implementation; they explain the
**absence** of findings rather than being findings themselves.

1. **Five-layer input validation in `parse()`** (src/.../_iso_ordinal_parse.py:154-200):
   - type check (str only)
   - sign extraction (one leading `-` only)
   - structural split (exactly one `-` separator)
   - per-part length + ASCII-digit check
   - value range check (year in `[-9999, 9999]`, day in `[1, days_in_year(year)]`)

2. **Explicit `bool` rejection** in `is_leap_year` / `days_in_year`
   (lines 106-109, 120-123). Without this guard, `isinstance(True, int)`
   would be True and `is_leap_year(True)` would return `is_leap_year(1) ==
   False` (a footgun avoided, not a vuln).

3. **3-digit day + 4-digit year gate** runs BEFORE `int()` conversion. So
   even 23-digit-year inputs (`"99999999999999999999999-060"`) are rejected
   by the structural gate without ever constructing a Python big-int.

4. **CLI uses `argparse`** (no `subprocess`, no `shell=True`, no `eval`).
   `main()` reads `args.value` / `args.validate` and passes them to `parse()`,
   which is the only string-consuming function.

5. **Zero dependencies** (`pyproject.toml` line 44: `dependencies = []`).
   No supply-chain risk from third-party packages. Stdlib only (`datetime`,
   `typing`, `argparse`, `json`, `sys`).

6. **`OrdinalDateParseError` is a `ValueError` subclass**
   (`_iso_ordinal_parse.py:74`), so callers can catch it as `ValueError` for
   generic validation handling. Verified by test_error_is_value_error_subclass.

7. **NamedTuple for `OrdinalDate`** (line 61) gives immutability and tuple
   unpacking for free. No `__setattr__`, no `__delattr__` overrides.

---

## Verdict

```
VERDICT: CLEAN (0 findings: 0 Critical, 0 High, 0 Medium, 0 Low, 0 Info)
```

The cycle_137 build of `iso-ordinal-pure` (commit 57a8cab) is **ready to
ship** from a security perspective. The 233-test suite is adequate for the
documented contract (12 LOCKED ACs verified). 9 defense-in-depth test gaps
were identified for T2/T3 to close, but none are exploitable vulnerabilities.

---

## Cross-cycle distinct verification

`iso-ordinal-pure` is the **first** ISO 8601 ordinal-date repository in the
repo-factory. It is family-member of `iso-weekdate-pure` (which parses
`YYYY-Www-D`) but with a DIFFERENT format (`YYYY-DDD` vs `YYYY-Www-D`). It
is NOT a wrapper around `datetime.strptime("%Y-%j")` (which would lose
leap-year validation and negative-year support — both of which are correctly
handled here). It is NOT a wrapper around `datetime.date.fromisoformat()`
(which rejects `YYYY-DDD` entirely). It correctly fills the gap identified
in SPEC §4.

This distinctness was confirmed in `cycle_137/discover` (t_2481f2bb) via
`check_existing.py VERDICT: APPROVED` and 5 primary-source URLs (HTTP 200
verified 2026-09-28). No cross-cycle contamination of findings.

---

## Observations (not findings — not counted in the severity tally above)

Two corrections/improvements were noticed during source review. Neither is
exploitable nor rises to "finding" severity, but they are recorded here so
that a future maintainer may address them:

### OBS-1 — Docstring drift: `is_leap_year` / `days_in_year`

**File:** `src/iso_ordinal_parse/_iso_ordinal_parse.py:103-105`, `:118`

The docstring says `bool` is accepted (because `bool` is a subclass of
`int`), but the implementation immediately below (lines 106, 120)
**rejects** `bool` via an explicit `isinstance(year, bool)` fence. Both
`is_leap_year(True)` and `days_in_year(True)` raise a clean `TypeError`
in the live probe.

**Why not a finding:** The *code* is correct — the bool-fence is a
deliberate defensive choice (a footgun avoided). The drift is purely
in the human-readable documentation. A future cycle may update the
docstring to say "bool is rejected (despite being a subclass of int)".

### OBS-2 — Console-script name vs argparse `prog`

**Files:** `pyproject.toml [project.scripts]` declares the binary as
`iso-ordinal-pure`; `src/iso_ordinal_parse/__main__.py:27,43` uses
`_PROGRAM = "iso-ordinal-parse"` and `argparse.ArgumentParser(prog=...)`.

After `pip install -e .`, `which iso-ordinal-pure` works but
`iso-ordinal-pure --help` shows `usage: iso-ordinal-parse [-h] ...`.

**Why not a finding:** Cosmetic UX confusion only. No security
implication; no behavior change would prevent user code from working.
A future cycle may align `_PROGRAM` with the pyproject script name.

---

## Audit artifacts

This audit produced 5 documents (all committed to
`benchmarks/adversarial/cycle_137/`):

| File | Purpose |
|---|---|
| `THREAT_MODEL.md` | Adversary model + 60+ probe results |
| `CWE_MAP.md` | 20 candidate CWEs evaluated; 3 apply and mitigated |
| `SURFACES.md` | Enumeration of every public API + CLI + module surface |
| `TEST_GAPS.md` | 9 defense-in-depth test improvements for T2/T3 |
| `VULN_AUDIT.md` | This file — final severity-ranked findings + verdict |

T2 (harness builder), T3 (seed corpus + fuzzer execution), T4 (triage),
and T5 (FUZZING_REPORT) are downstream of this audit and will validate or
invalidate the CLEAN verdict via empirical fuzzing. The CLEAN verdict is
a static assessment based on code review + live probing; the fuzzing
phases will provide empirical confirmation.

---

VERDICT: CLEAN (0 findings: 0 Critical, 0 High, 0 Medium, 0 Low, 0 Info)