# Test Gaps — iso-ordinal-pure

**Repo:** iso-ordinal-pure
**Cycle:** 137 / T1 (manual vulnerability audit)
**Existing test count:** 233 (87 def + 146 parametrizations; all passing)
**Methodology:** For each adversarial vector in `THREAT_MODEL.md`, identify
whether the 233-test suite covers it. Document gaps as recommendations for
**T2 (harness builder)** to close.

---

## Summary

| Section | Gap count | Severity for T2/T3 |
|---|---|---|
| §1 Parse-surface gaps | 5 | Medium — closer the gap, stronger the audit |
| §2 CLI-surface gaps | 4 | Low — defense-in-depth, not exploitable |
| §3 Cosmetic (NOT a vuln) | 1 | Info — note for spec compliance |
| **Total exploitable gaps** | **0** | The 233-test suite passes; CLEAN verdict stands. |

The gaps below are **defense-in-depth improvements** the next adversary cycle
should target via the fuzzer (T2/T3/T4). None are exploitable findings.

---

## §1. Parse-surface test gaps

### §1.1 Binary / null-byte / control-character inputs

**Threat model reference:** THREAT_MODEL.md §4 — V7-binary vectors.

**Current coverage:** 0 explicit tests.

**Existing implicit coverage:** None. The 21-error-substring parametrization
in `TestErrorMessages` (lines 350-373) covers leading/trailing whitespace,
alpha, dot, double-dash, etc. — but NOT control characters like `\x00`,
`\r`, `\n` embedded inside the value.

**Recommended test additions (for T2 harness):**

```python
@pytest.mark.parametrize("value", [
    "2024\x00-060",     # null byte in year
    "2024\n-060",       # newline in year
    "2024\r-060",       # CR in year
    "2024\t-060",       # tab in year
    "2024-\x00060",     # null byte in day
    "2024-\n060",       # newline in day
    "\x002024-060",     # null byte at start
])
def test_parse_control_chars(value: str) -> None:
    with pytest.raises(OrdinalDateParseError):
        parse(value)
```

**Live evidence:** All 7 inputs raise clean `OrdinalDateParseError("bad format:
year/day part ... must be exactly 4/3 digits")` (audit probes 2026-09-28).

---

### §1.2 Unicode non-ASCII digit confusion

**Threat model reference:** THREAT_MODEL.md §4 — V8-unicode vectors.

**Current coverage:** 0 explicit tests.

**Existing implicit coverage:** None. The `_is_valid_int` check (line 135:
`"0" <= c <= "9"` ASCII range) implicitly rejects Unicode digits, but no
test asserts it explicitly.

**Recommended test additions (for T2 harness):**

```python
@pytest.mark.parametrize("value", [
    "\u0662\u0660\u0662\u0664-\u0660\u0666\u0660",   # Arabic-Indic
    "\uFF12\uFF10\uFF12\uFF14-\uFF10\uFF16\uFF10",   # Fullwidth
    "\u0966\u0966\u0966\u0966-\u0966\u0966\u0966",   # Devanagari
    "\u06F1\u06F2\u06F3\u06F4-\u06F1\u06F2\u06F3",   # Ext-Arabic
    "\u0032\u0660\u0662\u0664-\u0660\u0666\u0660",   # mixed ASCII + Arabic
    "\u2024-060",                                     # ONE DOT LEADER (not even a digit)
])
def test_parse_unicode_digits_rejected(value: str) -> None:
    with pytest.raises(OrdinalDateParseError, match="bad format"):
        parse(value)
```

**Live evidence:** All 6 inputs raise clean `OrdinalDateParseError` (audit
probes 2026-09-28).

---

### §1.3 Massive day-of-year value (5+ digits)

**Threat model reference:** THREAT_MODEL.md §4 — V1-massive-day vectors.

**Current coverage:** The 3-digit gate rejects these, but no explicit test
for `parse("2024-99999")`, `parse("2024-999999999")`, or `parse("2024-10000")`.

**Existing implicit coverage:** `"2026-1000"` (4-digit day, line 360) covers
the principle — the 3-digit check rejects > 3 chars — but doesn't document
the specific `99999` / `999999999` / `10000` rejection paths.

**Recommended test additions:**

```python
@pytest.mark.parametrize("value", [
    "2024-99999",
    "2024-999999",
    "2024-999999999",
    "2024-10000",
])
def test_parse_huge_day_rejected(value: str) -> None:
    with pytest.raises(OrdinalDateParseError, match="bad format"):
        parse(value)
```

**Live evidence:** All 4 inputs raise clean `OrdinalDateParseError("bad format:
day part '...' must be exactly 3 digits")`.

---

### §1.4 Year 0 (proleptic Gregorian edge) + `to_date()` rejection

**Threat model reference:** THREAT_MODEL.md §4 — V4-year-zero vectors.

**Current coverage:** `parse("0000-001")` is implicitly covered by the
happy-path corpus (it would parse successfully), but:

- No test asserts that `format(parse("0000-001")) == "0000-001"`.
- No test asserts that `parse("-0000-060")` returns `OrdinalDate(0, 60)`
  (the `-` is consumed but year part is `0000` → 0; sign × 0 = 0).
- No test asserts that `to_date(parse("0000-001"))` raises
  `OrdinalDateParseError` because stdlib `datetime.date` requires year ≥ 1.
- No test asserts that `to_date(parse("-0044-060"))` raises
  `OrdinalDateParseError` (BCE rejected).
- The fuzz test (TestFuzzProperty, line 579) **explicitly skips year 0** with
  the comment `# skip year=0 and some, target ~1000 actual runs`.

**Recommended test additions:**

```python
def test_year_0_round_trip() -> None:
    od = parse("0000-001")
    assert od == OrdinalDate(0, 1)
    assert format(od) == "0000-001"
    assert is_leap_year(0) is True  # proleptic: year 0 divisible by 400

def test_year_0_to_date_rejected() -> None:
    """datetime.date requires year >= 1; to_date() must raise cleanly."""
    od = parse("0000-001")
    with pytest.raises(OrdinalDateParseError, match="cannot convert BCE year"):
        to_date(od)

def test_bce_to_date_rejected() -> None:
    od = parse("-0044-060")
    with pytest.raises(OrdinalDateParseError, match="cannot convert BCE year"):
        to_date(od)

def test_minus_zero_normalizes_to_zero() -> None:
    """-0000 has the sign bit consumed; result is year=0 (same as 0000)."""
    od = parse("-0000-060")
    assert od.year == 0
    assert format(od) == "0000-060"
```

**Live evidence:** All 4 behaviors verified live during audit (2026-09-28).
The 4-digit-year check `len(year_str) == 4` means `-0000` parses with `year_str
= "0000"` → year = -1 × 0 = 0, day = 60. Confirmed by probe.

---

### §1.5 `is_leap_year` / `days_in_year` bool-rejection

**Threat model reference:** THREAT_MODEL.md §4 — V5/V8 type-error vectors.

**Current coverage:** TestTypeErrorSafety covers general type errors
(None, list, dict, etc.) but does NOT explicitly parametrize `True` and
`False` for `is_leap_year` / `days_in_year`. The code explicitly rejects
bool with a guard `isinstance(year, bool)` (lines 106, 120).

**Recommended test additions:**

```python
@pytest.mark.parametrize("bad", [True, False])
def test_is_leap_year_rejects_bool(bad: object) -> None:
    with pytest.raises(TypeError, match="expected int"):
        is_leap_year(bad)  # type: ignore[arg-type]

@pytest.mark.parametrize("bad", [True, False])
def test_days_in_year_rejects_bool(bad: object) -> None:
    with pytest.raises(TypeError, match="expected int"):
        days_in_year(bad)  # type: ignore[arg-type]

@pytest.mark.parametrize("bad", [1.0, 1.5, 2.0])
def test_is_leap_year_rejects_float(bad: object) -> None:
    with pytest.raises(TypeError, match="expected int"):
        is_leap_year(bad)  # type: ignore[arg-type]
```

**Live evidence:** All 5 inputs raise clean `TypeError` (audit probes).

---

## §2. CLI-surface test gaps

### §2.1 Shell-metacharacter CLI input

**Current coverage:** 0 explicit tests. The `--validate` path is tested with
ordinary bad-format strings, but no test passes `"--validate", "; rm -rf /"`.

**Recommended test addition:**

```python
def test_cli_shell_metachar_rejected() -> None:
    """Shell metachars must not be interpreted; just parse as ordinary string."""
    result = _run_cli("--validate", "; rm -rf /")
    assert result.returncode == 1
```

**Live evidence:** `main(["--validate", "; rm -rf /"])` returns exit 1 with
`OrdinalDateParseError` — no shell execution path exists in `main()`.

---

### §2.2 Unicode-digit CLI input

**Current coverage:** 0 explicit tests.

**Recommended test addition:**

```python
@pytest.mark.parametrize("value", [
    "\u0662\u0660\u0662\u0664-\u0660\u0666\u0660",  # Arabic-Indic
    "\uFF12\uFF10\uFF12\uFF14-\uFF10\uFF16\uFF10",  # Fullwidth
])
def test_cli_unicode_digits_rejected(value: str) -> None:
    result = _run_cli("--validate", value)
    assert result.returncode == 1
```

**Live evidence:** Both inputs return exit 1 (audit probes).

---

### §2.3 Large argv (DoS stress)

**Current coverage:** 0 explicit tests. Cat-H tests use ≤10-char strings.

**Recommended test addition:**

```python
def test_cli_huge_argv_does_not_hang() -> None:
    """1MB argv must not crash or hang."""
    import time
    start = time.monotonic()
    result = _run_cli("--validate", "A" * 1_000_000)
    elapsed = time.monotonic() - start
    assert result.returncode == 1
    assert elapsed < 1.0, f"parse() took {elapsed}s on 1MB input"
```

**Live evidence:** `main(["--validate", "A"*1_000_000])` returned exit 1 in
<100ms on Linux 6.12 + Python 3.11.15.

---

### §2.4 CLI BCE year via positional arg with `--` separator

**Current coverage:** 0 explicit tests. The `_USAGE` text mentions `-- -0044-007`
but no test actually invokes this pattern.

**Recommended test addition:**

```python
def test_cli_positional_bce_year_with_dashdash() -> None:
    """Pass BCE year via positional arg using ``--`` to bypass argparse flag parsing."""
    result = _run_cli("--", "-0044-007")
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["year"] == -44
    assert payload["day_of_year"] == 7
```

---

## §3. Cosmetic (NOT a vulnerability) — info only

### §3.1 Console-script binary name vs argparse prog mismatch

**Observation:** `pyproject.toml [project.scripts]` exports the binary as
`iso-ordinal-pure`, but `_PROGRAM = "iso-ordinal-parse"` in `__main__.py` and
`argparse.ArgumentParser(prog="iso-ordinal-parse")` display the program as
`iso-ordinal-parse`. So:

- `which iso-ordinal-pure` → works after install
- `iso-ordinal-pure --version` → prints `iso-ordinal-parse 0.1.0`
- `iso-ordinal-pure --help` → `usage: iso-ordinal-parse [-h] ...`

**Impact:** Cosmetic confusion, NOT a security finding. A user might think
the binary isn't installed correctly because the help text shows a different
name.

**Recommended fix (out of T1 scope, for T2/T3 to note):** Align `_PROGRAM`
and `argparse.prog` to the pyproject script name (`iso-ordinal-pure`). One-line
change.

**Documentation alignment (NOT a code change):** The README's Quick Start
correctly uses `python -m iso_ordinal_parse` (line 105-114), which is
independent of the script name and works regardless. So this is purely a
display-string issue, not a docs bug.

---

## §4. Closing-the-loop instructions for T2 (harness builder)

T2 should write fuzz harnesses that target §1 and §2 gaps specifically:

1. **`fuzz_parse_malformed.py`** — Atheris / libFuzzer harness for `parse()`.
   Seed corpus:
   - ASCII malformed (`"2024-99999"`, `"abcd-efg"`, `"2024--060"`, `""`,
     `"  "`, `"2024-"`, `"--2024"`)
   - Whitespace variants (`" 2024-060"`, `"2024-060 "`, `"2024- 060"`,
     `"2024\t-060"`)
   - Control-char variants (`"2024\x00-060"`, `"2024\n-060"`, `"2024\r-060"`)
   - Unicode-digit variants (each script's digits × common years/days)
   - Oversized (`"A"*10000 + "-060"`, `"2024-" + "A"*10000`)

2. **`fuzz_parse_roundtrip.py`** — Differential fuzzer. Parse every
   fuzz-generated input; for those that succeed, assert `format(od) ==
   original_input` AND `to_date(od)` round-trips through `from_date`.

3. **`fuzz_type_errors.py`** — Fuzz every public function with type-confused
   inputs (None, int, float, str, bytes, list, dict, tuple, bool, custom
   class). Expect every call to raise `TypeError` cleanly.

4. **`fuzz_cli.py`** — Subprocess fuzzer for the CLI. Seed corpus with
   `--validate VALUE`, `--version`, `--help`, no-args, plus the malformed
   inputs above. Expect: exit 0/1, never a hang or crash.

5. **`fuzz_big_int.py`** — Fuzz `is_leap_year` and `days_in_year` with random
   Python ints from 10**0 to 10**10000. Expect: O(1) wall-time, clean
   `OrdinalDateParseError` on OOR year, correct result for valid year.

---

VERDICT: 9 defense-in-depth test gaps, **0 exploitable vulnerabilities**.