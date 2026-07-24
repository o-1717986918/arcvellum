"""Compatibility alias for :mod:`.projections.narrative_projection`."""

import sys

from .projections import narrative_projection as _implementation

sys.modules[__name__] = _implementation
