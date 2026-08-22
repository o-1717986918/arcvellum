"""Compatibility alias for :mod:`.projections.narrative_projection_v4`."""

import sys

from .projections import narrative_projection_v4 as _implementation

sys.modules[__name__] = _implementation
