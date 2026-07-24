"""Compatibility alias for :mod:`.projections.api_read_models`."""

import sys

from .projections import api_read_models as _implementation

sys.modules[__name__] = _implementation
