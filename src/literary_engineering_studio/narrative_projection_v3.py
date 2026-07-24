"""Compatibility alias for :mod:`.projections.narrative_projection_v3`."""

import sys

from .projections import narrative_projection_v3 as _implementation

sys.modules[__name__] = _implementation
