"""pytest configuration for iso-ordinal-pure tests.

Adds ``src/`` to ``sys.path`` so tests can ``import iso_ordinal_parse``
without an editable install. CI and local runs should set
``PYTHONPATH=src`` for consistency.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))