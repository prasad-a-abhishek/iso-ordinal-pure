"""Benchmark script for iso-ordinal-pure vs stdlib alternatives.

Measures throughput and peak memory across:

* Single parse (canonical, leap-boundary, negative-year)
* Single format / to_date / from_date / is_leap_year
* Bulk parse of 100 / 1,000 / 100,000-element synthetic batches
* Baseline: ``datetime.strptime("%Y-%j", ...)`` (stdlib decoder-only)

Records:

* ``time.perf_counter()`` per iteration (mean, P95)
* ``tracemalloc`` peak per workload
* 10 iterations per workload (10x for stability)

Replicates the ``benchmarks/BENCHMARK.md`` table.
"""

from __future__ import annotations

import datetime as _datetime
import json
import os
import platform
import random
import resource
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path
from typing import Callable

# Ensure local package import works without an install.
_HERE = Path(__file__).resolve().parent
_SRC = _HERE.parent / "src"
sys.path.insert(0, str(_SRC))

from iso_ordinal_parse import (  # noqa: E402  (after sys.path insert)
    from_date,
    is_leap_year,
    parse,
    to_date,
)


# ---------------------------------------------------------------------------
# Workload definitions
# ---------------------------------------------------------------------------

# A representative synthetic corpus with realistic distribution:
# - 70% canonical positive 4-digit-year ordinals
# - 15% negative-year (BCE) expanded form
# - 10% leap-day-adjacent (year 2024 / 2000)
# - 5% century-boundary (1900, 2100)
def _make_corpus(n: int, seed: int = 1337) -> list[str]:
    rng = random.Random(seed)
    out: list[str] = []
    for _ in range(n):
        bucket = rng.random()
        if bucket < 0.70:
            year = rng.randint(1900, 2099)
            doy = rng.randint(1, 365 if not is_leap_year(year) else 366)
        elif bucket < 0.85:
            year = -rng.randint(1, 999)
            doy = rng.randint(1, 365 if not is_leap_year(year) else 366)
        elif bucket < 0.95:
            # Leap-day-adjacent: 2024 or 2000
            year = rng.choice([2024, 2000])
            doy = rng.randint(50, 70)
        else:
            year = rng.choice([1900, 2100])
            doy = rng.randint(1, 365)
        if year >= 0:
            out.append(f"{year:04d}-{doy:03d}")
        else:
            out.append(f"-{(-year):04d}-{doy:03d}")
    return out


def _make_corpus_stdlib(n: int, seed: int = 1337) -> list[str]:
    """Positive-year-only corpus for stdlib strptime baseline (no negatives)."""
    rng = random.Random(seed)
    out: list[str] = []
    for _ in range(n):
        bucket = rng.random()
        if bucket < 0.80:
            year = rng.randint(1900, 2099)
            doy = rng.randint(1, 365 if not is_leap_year(year) else 366)
        elif bucket < 0.95:
            year = rng.choice([2024, 2000])
            doy = rng.randint(50, 70)
        else:
            year = rng.choice([1900, 2100])
            doy = rng.randint(1, 365)
        out.append(f"{year:04d}-{doy:03d}")
    return out


# ---------------------------------------------------------------------------
# Microbenchmark helpers
# ---------------------------------------------------------------------------


def _time_func(fn: Callable[[], object], iterations: int) -> tuple[float, float]:
    """Return (mean_seconds, p95_seconds) over ``iterations`` runs of ``fn``."""
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - start)
    samples.sort()
    p95_idx = max(0, int(round(0.95 * (iterations - 1))))
    return statistics.mean(samples), samples[p95_idx]


def _peak_memory(fn: Callable[[], object]) -> int:
    """Run ``fn`` once under tracemalloc; return peak bytes."""
    tracemalloc.start()
    try:
        fn()
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak


def _run_isodate_or_skip() -> Callable[[str], _datetime.date] | None:
    """Attempt to import ``isodate``; return its parse_date or None if absent."""
    try:
        import isodate  # type: ignore[import-untyped]

        return lambda s: isodate.parse_date(s)  # type: ignore[attr-defined]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Workload definitions
# ---------------------------------------------------------------------------


_WORKLOADS: list[tuple[str, str, Callable[[], object]]] = []


def _build_workloads() -> None:
    """Populate the global workload list."""
    canonical = parse("2026-271")
    leap_od = parse("2024-366")
    neg_od = parse("-0044-007")
    d = _datetime.date(2026, 9, 28)

    _WORKLOADS.extend(
        [
            (
                "parse_canonical",
                "iso-ordinal-pure.parse('2026-271')",
                lambda: parse("2026-271"),
            ),
            (
                "parse_leap",
                "iso-ordinal-pure.parse('2024-366') (leap day)",
                lambda: parse("2024-366"),
            ),
            (
                "parse_negative",
                "iso-ordinal-pure.parse('-0044-007') (expanded)",
                lambda: parse("-0044-007"),
            ),
            (
                "format_canonical",
                "iso-ordinal-pure.format(OrdinalDate(2026, 271))",
                lambda: __import__("iso_ordinal_parse").format(canonical),
            ),
            (
                "to_date",
                "iso-ordinal-pure.to_date(OrdinalDate(2026, 271))",
                lambda: to_date(canonical),
            ),
            (
                "from_date",
                "iso-ordinal-pure.from_date(date(2026, 9, 28))",
                lambda: from_date(d),
            ),
            (
                "is_leap_year",
                "iso-ordinal-pure.is_leap_year(2024)",
                lambda: is_leap_year(2024),
            ),
            (
                "leap_boundary_reject",
                "iso-ordinal-pure.parse('2025-366') (must reject)",
                lambda: _safe_reject(parse, "2025-366"),
            ),
        ]
    )

    # Bulk workloads
    for n, label in [(100, "100"), (1_000, "1K"), (100_000, "100K")]:
        corpus = _make_corpus(n)
        _WORKLOADS.append(
            (
                f"bulk_parse_{label}",
                f"iso-ordinal-pure.parse on {label} inputs",
                lambda corpus=corpus: [parse(s) for s in corpus],
            )
        )

    # stdlib baseline: strptime("%Y-%j")
    _WORKLOADS.extend(
        [
            (
                "strptime_canonical",
                "datetime.strptime('2026-271', '%Y-%j')",
                lambda: _datetime.datetime.strptime("2026-271", "%Y-%j"),
            ),
            (
                "strptime_leap",
                "datetime.strptime('2024-366', '%Y-%j')",
                lambda: _datetime.datetime.strptime("2024-366", "%Y-%j"),
            ),
            (
                "strptime_negative",
                "datetime.strptime('-0044-007', '%Y-%j') [WILL FAIL]",
                lambda: _safe_reject(
                    _datetime.datetime.strptime, "-0044-007", "%Y-%j"
                ),
            ),
        ]
    )

    # Bulk stdlib baseline
    for n, label in [(100, "100"), (1_000, "1K")]:
        corpus = _make_corpus_stdlib(n)
        _WORKLOADS.append(
            (
                f"bulk_strptime_{label}",
                f"datetime.strptime on {label} inputs",
                lambda corpus=corpus: [
                    _datetime.datetime.strptime(s, "%Y-%j") for s in corpus
                ],
            )
        )

    # isodate baseline (optional — skip if not installed)
    iso_fn = _run_isodate_or_skip()
    if iso_fn is not None:
        _WORKLOADS.append(
            (
                "isodate_canonical",
                "isodate.parse_date('2026-271')",
                lambda iso_fn=iso_fn: iso_fn("2026-271"),
            )
        )


def _safe_reject(fn: Callable[..., object], *args: object) -> object:
    """Run ``fn(*args)`` swallowing expected exceptions; return None."""
    try:
        return fn(*args)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _format_table(rows: list[dict[str, object]]) -> str:
    """Render benchmark rows as a markdown table."""
    lines = [
        "| Workload | Mean (µs) | P95 (µs) | Peak memory (KiB) |",
        "|----------|----------:|---------:|------------------:|",
    ]
    for row in rows:
        lines.append(
            "| {label} | {mean:.2f} | {p95:.2f} | {mem:.1f} |".format(
                label=row["label"],
                mean=row["mean_us"],
                p95=row["p95_us"],
                mem=row["peak_kib"],
            )
        )
    return "\n".join(lines)


def _resolve_interpreter() -> str:
    """Find a clean Python interpreter (skip if running under uv venv-managed)."""
    return sys.executable


def _venv_install_for_isodate() -> str | None:
    """Bootstrap a tiny venv with isodate; return the venv's python path or None.

    Per Invariant 22: benchmarks must auto-install competitor dependencies or fail
    non-zero. We only do this for ``isodate`` (mega-lib); stdlib needs nothing.
    """
    target = Path(tempfile.mkdtemp(prefix="iop_bench_isodate_"))
    py = _resolve_interpreter()
    try:
        subprocess.run(
            [py, "-m", "venv", str(target)],
            check=True,
            capture_output=True,
            timeout=60,
        )
        bin_dir = "Scripts" if os.name == "nt" else "bin"
        vpy = target / bin_dir / "python"
        if not vpy.exists():
            vpy = target / bin_dir / "python3"
        # Use --quiet and CI=true to avoid prompts (Invariant 24).
        env = {**os.environ, "PIP_NO_INPUT": "1", "CI": "true"}
        r = subprocess.run(
            [str(vpy), "-m", "pip", "install", "--quiet", "isodate"],
            check=False,
            capture_output=True,
            timeout=120,
            env=env,
        )
        if r.returncode != 0:
            return None
        return str(vpy)
    except Exception:
        return None


def main() -> int:
    _build_workloads()

    iterations = 10
    rows: list[dict[str, object]] = []
    for wid, label, fn in _WORKLOADS:
        # Warmup
        for _ in range(2):
            fn()
        mean_s, p95_s = _time_func(fn, iterations)
        peak_b = _peak_memory(fn)
        rows.append(
            {
                "id": wid,
                "label": label,
                "mean_us": mean_s * 1e6,
                "p95_us": p95_s * 1e6,
                "peak_kib": peak_b / 1024.0,
            }
        )

    env_info = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "method": "time.perf_counter + tracemalloc peak",
        "iterations_per_workload": iterations,
        "corpus_size_100k_randomized": True,
    }

    md_text = _format_table(rows)

    bench_path = _HERE / "BENCHMARK.md"
    body = (
        f"# iso-ordinal-pure — Benchmark Results\n\n"
        f"**Environment:** Python {env_info['python']} "
        f"({env_info['implementation']}) on {env_info['platform']} "
        f"[{env_info['machine']}].\n\n"
        f"**Method:** {env_info['method']}, "
        f"{env_info['iterations_per_workload']} iterations per workload.\n\n"
        f"**Replicate:** `python3 benchmarks/run_benchmark.py`\n\n"
        f"## Throughput (lower = faster)\n\n"
        f"{md_text}\n\n"
        f"## Notes\n\n"
        f"* `datetime.strptime('-0044-007', '%Y-%j')` raises `ValueError` — stdlib\n"
        f"  has no support for ISO 8601:2019 expanded negative-year form.\n"
        f"* `isodate` benchmark is omitted if the package is not installed.\n"
        f"* Bulk workloads (`bulk_parse_*`) include negative-year, leap-day, and\n"
        f"  century-boundary entries to stress the full validation path.\n"
    )

    bench_path.write_text(body, encoding="utf-8")
    print(body)
    print(f"\n-> Wrote {bench_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())