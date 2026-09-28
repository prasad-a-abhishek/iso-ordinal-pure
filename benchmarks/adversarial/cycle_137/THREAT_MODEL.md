# Threat Model — iso-ordinal-pure

**Repo:** iso-ordinal-pure (ISO 8601:2019 §4.4.2 ordinal date `YYYY-DDD`)
**Cycle:** 137 / T1 (manual vulnerability audit)
**Auditor:** repo-adversary (default profile)
**Audit date:** 2026-09-28
**Audited commit:** 57a8cab (cycle_137/qa VERDICT:SHIP)

---

## 1. Attacker model

### 1.1 Who is the adversary?

The realistic adversary for this library is **NOT** a remote attacker. `iso-ordinal-pure`
is a pure-Python parser library with zero runtime dependencies and a single-user CLI.
There is no network surface, no file I/O, no subprocess invocation, no SQL, no eval,
no `pickle`, no `os.system` / `subprocess.Popen` / `shell=True` anywhere in the code.
The realistic adversary profile is:

1. **Downstream ingest pipeline that feeds untrusted strings.** A backend service
   ingesting NOAA EOSDIS products, aviation METAR reports, or fiscal-calendar data
   passes strings straight from a network or file source into `parse()`. A malformed
   input could (a) cause a crash, hanging the ingest worker, or (b) cause silent
   mis-interpretation of the date (off-by-one, leap-year miscalculation) that
   silently corrupts downstream reports. The adversary here is **a misbehaving
   upstream producer**, not a deliberate attacker.

2. **CLI user passing arbitrary CLI arguments.** A user (or a script) may invoke
   `iso-ordinal-parse` on untrusted strings. The CLI must (a) reject malformed
   input with a useful error and non-zero exit, (b) never execute shell, (c)
   never crash with an uncaught traceback for any string-shaped input.

3. **Library user importing `iso_ordinal_parse` from untyped data.** They might
   pass `None`, `12345`, `[]`, or a `datetime` instead of a `str`. The library
   must raise a clean `TypeError` per the public type signature (`parse(value: str)`).

### 1.2 Trust boundary

```
                ┌──────────────────────┐
  untrusted ──▶ │  parse() / CLI input │  ──▶ trusted OrdinalDate
  string        │  (zero-dep parser)   │      (year, day_of_year)
                └──────────────────────┘
                          │
                          ▼
                  to_date(od) ──▶ datetime.date (stdlib)
                  format(od)  ──▶ str
                  from_date(d)──▶ OrdinalDate
```

The parser is the **only entry point** where untrusted bytes enter the trusted
domain. After `parse()` returns a validated `OrdinalDate`, the year and
day_of_year are guaranteed by construction to be in the supported range
(`-9999..9999`, `1..days_in_year(year)`).

### 1.3 Worst-case impact

| Failure mode | Severity | Rationale |
|---|---|---|
| Uncaught exception (crash) in ingest pipeline | Medium | DoS / data loss for one input; pipelined worker crashes; queue may stall |
| Silent mis-parse (off-by-one, leap-year misclass) | **High** for downstream correctness | Wrong date in METAR log, settlement record, or fiscal report — silent corruption is worse than crash |
| Code execution via parser | n/a | Not reachable: no `eval`, no `pickle`, no `subprocess`, no `os.system`; pure string ops |
| Memory exhaustion via huge year int | Low | `parse()` rejects at the 4-digit-format gate before any large-int computation; `is_leap_year` accepts any int but modulo is O(1) |
| CLI shell injection | n/a | `argparse` is a pure argv parser; no shell exec anywhere |

The realistic worst case is **silent date corruption** from a parser bug (e.g.
accepting day 366 in non-leap year like `strptime("%Y-%j")` does), which the
QA suite already verified does NOT happen (AC3 + Cat-E leap-year tests).

---

## 2. Trust assumptions (positive)

The audit confirms these pre-conditions from the source and tests:

1. `parse()` is the only public function that takes an attacker-controlled string.
2. `parse()` validates the input shape (must be str) before any string ops.
3. `parse()` validates the structural format (4-digit year, 3-digit day, exactly
   one dash separator) before parsing ints.
4. `parse()` validates the value ranges (`-9999 ≤ year ≤ 9999`, `1 ≤ day ≤ days_in_year(year)`).
5. After `parse()` returns, `OrdinalDate` is constructed from validated ints — no
   further untrusted-string surface.
6. `to_date()` / `from_date()` / `format()` operate only on already-validated `OrdinalDate`
   or stdlib `datetime.date`, both trusted-domain types.
7. `is_leap_year` and `days_in_year` take an `int`; type-mismatched input raises
   `TypeError` cleanly (Invariant 21).
8. `__main__.main()` uses `argparse` (no shell exec), catches `OrdinalDateParseError`
   in `--validate` mode (returns exit 1), re-raises in default mode (caller sees
   the reason). Unknown flags return non-zero from argparse. No flags print stack
   traces.
9. The package has `dependencies = []` and imports only `datetime` and stdlib `typing`.

---

## 3. Adversary capability matrix

| Capability | Reachable? | How? |
|---|---|---|
| Pass `None` to `parse()` | Yes | `parse(None)` raises `TypeError("parse() expected str, got NoneType")` |
| Pass non-string iterable to `parse()` | Yes | `parse([...])` raises `TypeError` |
| Pass a 100k-char string | Yes | Rejected at format gate (split on `-` produces ≠ 2 parts or year part > 4 chars) |
| Pass Unicode digits | Yes | Rejected at format gate (`0 ≤ c ≤ 9` ASCII range check, line 135 of `_iso_ordinal_parse.py`) |
| Pass binary input (bytes) | Yes | `TypeError("parse() expected str, got bytes")` |
| Inject shell metacharacters via CLI | Yes (attempt) | `argparse` stores as a literal string; `main()` passes to `parse()`; no `os.system` / `subprocess` / `shell=True` |
| Crash via huge int in `is_leap_year` | Yes | `is_leap_year(10**1000)` returns `True` in O(1) (modulo is constant-time on big ints in CPython); no OOM |
| Crash via huge int in `days_in_year` | Yes | `days_in_year(10**100)` raises `OrdinalDateParseError("year out of range")` (no allocation) |
| Force uncaught exception | Yes (attempt) | Live audit ran 60+ adversarial inputs; **zero** uncaught exceptions, zero crashes |
| Trigger infinite loop | n/a | `parse()` is O(n) on input length with a fixed split+integer-parse; no recursion, no backtracking |

---

## 4. Negative findings (NOT vulnerabilities)

These were explicitly probed and behaved correctly. Documented here so the next
adversary cycle doesn't re-investigate them.

| Probe | Expected behavior | Observed behavior | Status |
|---|---|---|---|
| `parse(None)` | `TypeError` | `TypeError: parse() expected str, got NoneType` | OK |
| `parse(12345)` | `TypeError` | `TypeError: parse() expected str, got int` | OK |
| `parse([])` | `TypeError` | `TypeError: parse() expected str, got list` | OK |
| `parse(b"2024-060")` | `TypeError` | `TypeError: parse() expected str, got bytes` | OK |
| `parse("")` | `OrdinalDateParseError("bad format")` | OK | OK |
| `parse("   ")` | `OrdinalDateParseError("bad format")` | OK | OK |
| `parse("\t")`, `parse("\n")` | `OrdinalDateParseError` | OK | OK |
| `parse("2024\x00-060")` | `OrdinalDateParseError` (control char in year part) | OK | OK |
| `parse("\u0662\u0660\u0662\u0664-\u0660\u0666\u0660")` (Arabic-Indic digits) | `OrdinalDateParseError` (year part `٢٠٢٤` rejected as non-ASCII) | OK | OK |
| `parse("\uFF12\uFF10\uFF12\uFF14-\uFF10\uFF16\uFF10")` (Fullwidth digits) | `OrdinalDateParseError` | OK | OK |
| `parse("2024- 060")` (internal ws) | `OrdinalDateParseError` | OK | OK |
| `parse(" 2024-060")` (leading ws) | `OrdinalDateParseError` | OK | OK |
| `parse("2024-060 ")` (trailing ws) | `OrdinalDateParseError` | OK | OK |
| `parse("2024--060")` (double dash) | `OrdinalDateParseError` | OK | OK |
| `parse("--2024-060")` (double minus) | `OrdinalDateParseError` | OK | OK |
| `parse("2024-99999")` (5-digit day) | `OrdinalDateParseError` (day part length ≠ 3) | OK | OK |
| `parse("9999999999-060")` (10-digit year) | `OrdinalDateParseError` (year part length ≠ 4) | OK | OK |
| `parse("99999999999999999999999-060")` (huge year) | `OrdinalDateParseError` (year part length ≠ 4, rejected before int parse) | OK | OK |
| `parse("2024-1000")` (4-digit day) | `OrdinalDateParseError` (day part length ≠ 3) | OK | OK |
| `parse("-0044-060")` (AC4) | accept → `OrdinalDate(-44, 60)` | OK | OK |
| `parse("0000-001")` (year 0) | accept → `OrdinalDate(0, 1)`; `to_date()` rejects with `OrdinalDateParseError("cannot convert BCE year 0")` | OK | OK |
| `parse("1900-366")` (century non-leap) | `OrdinalDateParseError("day out of range")` | OK | OK |
| `parse("2000-366")` (century by 400) | accept | OK | OK |
| `parse("2024-366")` (regular leap) | accept | OK | OK |
| `parse("2100-366")` (future century non-leap) | `OrdinalDateParseError` | OK | OK |
| `parse("-9999-366")` (BCE max year, day 366) | `OrdinalDateParseError` (-9999 is NOT leap, day 366 OOR) | OK | OK |
| `format(OrdinalDate(-44, 7))` | `"-0044-007"` | OK | OK |
| `format(OrdinalDate(0, 1))` | `"0000-001"` | OK | OK |
| `format(None)` | `TypeError` | OK | OK |
| `format("2024-60")` | `TypeError` | OK | OK |
| `to_date(OrdinalDate(0, 1))` | `OrdinalDateParseError` (datetime.date requires year ≥ 1) | OK | OK |
| `to_date(parse("-0044-060"))` | `OrdinalDateParseError` (BCE rejected) | OK | OK |
| `to_date(None)` | `TypeError` | OK | OK |
| `from_date(None)` | `TypeError` | OK | OK |
| `from_date("2024-01-01")` | `TypeError` | OK | OK |
| `is_leap_year(True)` | `TypeError` (bool explicitly rejected) | OK | OK |
| `is_leap_year(1.0)` | `TypeError` | OK | OK |
| `is_leap_year("2024")` | `TypeError` | OK | OK |
| `is_leap_year(10**100)` | `True` (no crash, O(1) modulo) | OK | OK |
| `days_in_year(10000)` | `OrdinalDateParseError("year out of range")` | OK | OK |
| `days_in_year(10**100)` | `OrdinalDateParseError("year out of range")` (year OOR, no allocation) | OK | OK |
| `main(["2026-271"])` | exit 0, JSON `{year:2026, day_of_year:271, date:"2026-09-28"}` | OK | OK |
| `main(["--validate", "2026-999"])` | exit 1 | OK | OK |
| `main(["--validate=-0044-007"])` (BCE) | exit 0 | OK | OK |
| `main(["--validate", "; rm -rf /"])` (shell meta) | exit 1 (`OrdinalDateParseError`, no exec) | OK | OK |
| `main(["--validate", "\u0662\u0660\u0662\u0664-\u0660\u0666\u0660"])` (Arabic-Indic) | exit 1 (`OrdinalDateParseError`) | OK | OK |
| `main(["--bogus"])` (unknown flag) | argparse exits 2 (standard non-zero) | OK | OK |
| `main(["--validate", "A"*1_000_000])` (1MB argv) | exit 1 (`OrdinalDateParseError` "bad format: year part", no crash) | OK | OK |
| `main([])` (no args) | exit 0, usage on stderr | OK | OK |
| round-trip `format(parse(x)) == x` for 233 corpus entries | identity | OK | OK |

---

## 5. Residual risk assessment

**No exploitable vulnerability found** in the audited commit (57a8cab).

The realistic residual risks are:

1. **Cosmetic inconsistency** (Info): The console script is exported as
   `iso-ordinal-pure` (pyproject.toml `[project.scripts]`) but the argparse
   `prog` and `_PROGRAM` constant are `iso-ordinal-parse`. After `pip install -e .`,
   `which iso-ordinal-pure` works but `--help` shows `usage: iso-ordinal-parse`.
   Not a security finding — just confusing.

2. **BCE year semantics in `to_date()`** (Low, by design): `to_date()` raises
   `OrdinalDateParseError` for `year < 1` because stdlib `datetime.date` cannot
   represent BCE. This is documented in the docstring and is the correct
   behavior. Downstream code that needs BCE-as-`date` must use `format()` +
   manual calendar math or rely on the JSON output of the CLI (which has its own
   BCE branch using manual math).

3. **`is_leap_year(True)` / `is_leap_year(False)` raise `TypeError`** (Low, by
   design): Python `bool` is a subclass of `int`, so naive `isinstance(x, int)`
   would accept `True` and treat it as `1`. The code explicitly rejects `bool`.
   This is **defensive** — a footgun avoided, not a vulnerability.

---

VERDICT: CLEAN (0 findings of any severity)