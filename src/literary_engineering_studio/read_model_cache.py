"""Compatibility alias for :mod:`.projections.read_model_cache`."""

import sys

from .projections import read_model_cache as _implementation

sys.modules[__name__] = _implementation
