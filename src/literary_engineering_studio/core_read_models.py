"""Compatibility alias for :mod:`.projections.core_read_models`."""

import sys

from .projections import core_read_models as _implementation

sys.modules[__name__] = _implementation
