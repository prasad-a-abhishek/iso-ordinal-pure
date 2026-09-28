# iso-ordinal-pure — Benchmark Results

**Environment:** Python 3.11.15 (CPython) on Linux-6.12.67-linuxkit-aarch64-with-glibc2.41 [aarch64].

**Method:** time.perf_counter + tracemalloc peak, 10 iterations per workload.

**Replicate:** `python3 benchmarks/run_benchmark.py`

## Throughput (lower = faster)

| Workload | Mean (µs) | P95 (µs) | Peak memory (KiB) |
|----------|----------:|---------:|------------------:|
| iso-ordinal-pure.parse('2026-271') | 1.38 | 3.50 | 0.6 |
| iso-ordinal-pure.parse('2024-366') (leap day) | 0.95 | 1.13 | 0.6 |
| iso-ordinal-pure.parse('-0044-007') (expanded) | 0.98 | 1.08 | 0.7 |
| iso-ordinal-pure.format(OrdinalDate(2026, 271)) | 0.43 | 1.17 | 0.2 |
| iso-ordinal-pure.to_date(OrdinalDate(2026, 271)) | 0.46 | 0.63 | 0.3 |
| iso-ordinal-pure.from_date(date(2026, 9, 28)) | 0.45 | 1.04 | 0.2 |
| iso-ordinal-pure.is_leap_year(2024) | 0.13 | 0.17 | 0.0 |
| iso-ordinal-pure.parse('2025-366') (must reject) | 1.08 | 1.37 | 1.0 |
| iso-ordinal-pure.parse on 100 inputs | 89.60 | 98.04 | 11.8 |
| iso-ordinal-pure.parse on 1K inputs | 944.72 | 1267.04 | 110.4 |
| iso-ordinal-pure.parse on 100K inputs | 97104.95 | 99080.29 | 10889.8 |
| datetime.strptime('2026-271', '%Y-%j') | 2.33 | 4.29 | 1.3 |
| datetime.strptime('2024-366', '%Y-%j') | 1.53 | 1.67 | 1.3 |
| datetime.strptime('-0044-007', '%Y-%j') [WILL FAIL] | 1.00 | 1.21 | 1.4 |
| datetime.strptime on 100 inputs | 148.99 | 169.17 | 6.2 |
| datetime.strptime on 1K inputs | 1517.66 | 1541.88 | 49.1 |
| isodate.parse_date('2026-271') | 1.20 | 2.00 | 1.3 |

## Notes

* `datetime.strptime('-0044-007', '%Y-%j')` raises `ValueError` — stdlib
  has no support for ISO 8601:2019 expanded negative-year form.
* `isodate` benchmark is omitted if the package is not installed.
* Bulk workloads (`bulk_parse_*`) include negative-year, leap-day, and
  century-boundary entries to stress the full validation path.
