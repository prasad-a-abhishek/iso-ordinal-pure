"""iso-ordinal-pure — zero-dependency ISO 8601 ordinal date (``YYYY-DDD``)
parser, serializer, and converter.

See :mod:`iso_ordinal_parse._iso_ordinal_parse` for the algorithm. This
module re-exports the public API and pins the package version.
"""

from __future__ import annotations

from iso_ordinal_parse._iso_ordinal_parse import (
    OrdinalDate,
    OrdinalDateParseError,
    days_in_year,
    format,
    from_date,
    is_leap_year,
    parse,
    to_date,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "OrdinalDate",
    "OrdinalDateParseError",
    "parse",
    "format",
    "to_date",
    "from_date",
    "is_leap_year",
    "days_in_year",
]