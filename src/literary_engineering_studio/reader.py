"""Compatibility alias for :mod:`.projections.reader`."""

import sys

from .projections import reader as _implementation

sys.modules[__name__] = _implementation
