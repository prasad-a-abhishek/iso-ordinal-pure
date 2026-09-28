# CWE Map — iso-ordinal-pure

**Repo:** iso-ordinal-pure (ISO 8601:2019 §4.4.2 ordinal date `YYYY-DDD`)
**Cycle:** 137 / T1 (manual vulnerability audit)
**Methodology:** For each candidate CWE, document (i) why it was considered,
(ii) whether it applies to this codebase, (iii) the specific code location
that mitigates it (if applicable), and (iv) the live-probe evidence.

---

## CWE index — applicability matrix

| CWE | Title | Applies? | Why |
|---|---|---|---|
| CWE-20 | Improper Input Validation | **Yes — mitigated** | `parse()` rejects malformed input at multiple gates (str type, structural format, value range). All 60+ adversarial inputs probe passed cleanly. |
| CWE-22 | Path Traversal | **No** | Library does no file I/O. |
| CWE-78 | OS Command Injection | **No** | No `os.system`, `subprocess.Popen`, `eval`, or `exec`. `argparse` is pure argv parsing. CLI on `; rm -rf /` exits 1 with `OrdinalDateParseError`. |
| CWE-94 | Code Injection | **No** | No `eval`, no `exec`, no `pickle`, no `marshal`. `int(s)` only ever sees digits 0-9 (verified by `_is_valid_int`). |
| CWE-119 | Buffer Overflow | **No** | Python is memory-safe; no C extensions. |
| CWE-125 | Out-of-bounds Read | **No** | Python is memory-safe. `body.split("-")` produces a list bounded by input length. |
| CWE-190 | Integer Overflow / Wraparound | **No** | Python ints are unbounded. `is_leap_year(10**1000)` returns in O(1) without OOM. `parse()` rejects > 4-digit year BEFORE any large-int computation. |
| CWE-400 | Uncontrolled Resource Consumption (CPU) | **No** | `parse()` is O(n) on input length with a fixed split + per-part integer parse. No regex backtracking. CLI on 1MB argv exits cleanly in <100ms (live probe). |
| CWE-401 | Missing Release of Resource (memory leak) | **No** | Python is GC'd. No native handles. |
| CWE-405 | Asymmetric Resource Consumption | **No** | n/a for a parser with no auth/state. |
| CWE-440 | Expected Behavior Violation | **No** | Library behavior matches its documented contract (verified by 233 tests). |
| CWE-476 | NULL Pointer Dereference | **No** | Python is memory-safe; no `NULL`. |
| CWE-601 | Open Redirect | **No** | Library does no URL handling. |
| CWE-611 | XXE | **No** | Library does no XML parsing. |
| CWE-704 | Incorrect Type Conversion | **No — explicitly mitigated** | All public functions (`parse`, `format`, `to_date`, `from_date`, `is_leap_year`, `days_in_year`) raise clean `TypeError` for non-expected types (verified live: None, int, float, str, list, dict, bytes, tuple, bool). |
| CWE-770 | Allocation of Resources Without Limits | **No** | No large allocation paths. `_NONLEAP_MONTH_DAYS` is a fixed 12-tuple. |
| CWE-835 | Loop with Unreachable Exit Condition | **No** | No loops in `parse()`. `to_date()` walks 12 months max (bounded by `_NONLEAP_MONTH_DAYS`). |
| CWE-915 | Improperly Controlled Modification of Dynamically-Determined Object Attributes | **No** | No `__import__`, no `setattr`, no `getattr` on untrusted names. |
| CWE-1333 | Inefficient Regular Expression Complexity | **No** | No regex anywhere in `src/`. |
| CWE-1352 | Reliance on Component with Vulnerability | **No** | `dependencies = []`; only stdlib `datetime` and `typing`. |

---

## Detailed CWE analysis (applicable CWEs)

### CWE-20 — Improper Input Validation

**Status:** **MITIGATED** (multiple validation gates).

**Defense-in-depth layers (src/iso_ordinal_parse/_iso_ordinal_parse.py):**

1. **Type gate** (line 154-157): `isinstance(value, str)` → `TypeError` on non-str.
2. **Sign gate** (line 162-167): leading `-` consumed for BCE form; only one allowed (multi-dash rejected later).
3. **Structural gate** (line 170-186): `body.split("-")` must produce exactly 2 parts; each part must be exactly the right length (4 for year, 3 for day) AND all characters must be ASCII digits (line 131-135, `_is_valid_int`).
4. **Year-range gate** (line 191-194): year must be in `[-9999, 9999]`.
5. **Day-range gate** (line 196-200): `1 ≤ day ≤ days_in_year(year)` (accounting for leap year).

**Evidence:** All 60+ adversarial inputs from `THREAT_MODEL.md` §4 were probed
live; every malformed input was rejected at one of these five gates with a
specific `OrdinalDateParseError` message.

**Residual risk:** None. The five gates together cover every vector enumerated
in the threat model: type confusion, internal whitespace, control characters,
non-ASCII digits, oversized parts, structural malformations, OOR day, OOR year,
leap-vs-non-leap misclassification.

---

### CWE-704 — Incorrect Type Conversion

**Status:** **MITIGATED** (explicit `isinstance` type gates on every public function).

| Function | Expected type | Behavior on wrong type | Evidence |
|---|---|---|---|
| `parse(value)` | `str` | `TypeError("parse() expected str, got NoneType")` | Live probe: None, 12345, [], {}, b'...', (1,2) |
| `format(ordinal)` | `OrdinalDate` | `TypeError("format() expected OrdinalDate, got NoneType")` | Live probe: None, 12345, "2024-60", (2024,60), 3.14, [...] |
| `to_date(ordinal)` | `OrdinalDate` | `TypeError("to_date() expected OrdinalDate, got NoneType")` | Live probe: None, 12345, str, tuple, float |
| `from_date(d)` | `datetime.date` | `TypeError("from_date() expected datetime.date, got NoneType")` | Live probe: None, 12345, str, tuple, float, list |
| `is_leap_year(year)` | `int` (NOT bool) | `TypeError("is_leap_year() expected int, got NoneType")` | Live probe: None, 1.0, "2024", 1.5, True, False, [], {}, b'2024' |
| `days_in_year(year)` | `int` (NOT bool) | `TypeError("days_in_year() expected int, got NoneType")` | Live probe: None, 1.0, "2024", True, False, [...] |

**Notable:** `is_leap_year` and `days_in_year` explicitly check
`isinstance(year, bool)` and reject it (lines 106-109, 120-123) even though
`bool` is a subclass of `int`. This is defensive — a footgun (treating `True`
as year `1`) avoided, not a vulnerability.

---

### CWE-400 — Uncontrolled Resource Consumption (CPU)

**Status:** **MITIGATED** (no regex backtracking, bounded parsing).

**Parsing complexity:** O(n) on input length n, where n is bounded by argv
length (typically ≤ ARG_MAX ≈ 128KB on Linux, ≤ 256KB on macOS).

**Live evidence:** `main(["--validate", "A"*1_000_000])` (1MB argv) returned
exit code 1 with `OrdinalDateParseError("bad format: year part ...")` in <100ms
on this audit host (Linux 6.12, Python 3.11.15). No hang, no OOM.

**Loop bounds:** `to_date()` walks at most 12 months (`_NONLEAP_MONTH_DAYS` is
a 12-tuple). No recursion. No exponential paths.

**Big-int handling:** `is_leap_year(10**1000)` returns in O(1) because Python
int modulo is constant-time on small operands (and `10**1000 % 4 == 0` is fast).
`days_in_year(10**100)` raises immediately on the OOR check without allocating.

---

### CWE-190 — Integer Overflow

**Status:** **N/A** (Python ints are unbounded, no C extension code).

**Mitigation pre-emptively:** `parse()` rejects year strings longer than 4
digits BEFORE converting to `int`, so even `parse("99999999999999999999-060")`
is rejected by the format gate (line 179-182) without instantiating a big int.

---

### CWE-915 — Improperly Controlled Modification of Dynamically-Determined Object Attributes

**Status:** **N/A** — no dynamic attribute access on untrusted names.

`src/` contains no `setattr`, `getattr`, `__import__`, or `globals()` calls on
untrusted input. Verified by `grep -nE "setattr|getattr|__import__|globals\\(\\)"
src/iso_ordinal_parse/*.py` → 0 hits.

---

## CWE coverage statement

All 20 CWEs in the candidate list were evaluated. Of these:

- **3 apply and are mitigated:** CWE-20 (input validation), CWE-704 (type
  conversion), CWE-400 (resource consumption).
- **17 do not apply** to this codebase by construction (no I/O, no C extension,
  no dynamic dispatch, no regex, no auth).

No unmitigated CWE was identified.

---

VERDICT: CLEAN (0 findings)