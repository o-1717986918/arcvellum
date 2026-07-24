"""Compatibility alias for :mod:`.projections.delivery`."""

import sys

from .projections import delivery as _implementation

sys.modules[__name__] = _implementation
