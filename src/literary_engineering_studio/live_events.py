"""Compatibility alias for :mod:`.observability.live_events`."""

import sys

from .observability import live_events as _implementation

sys.modules[__name__] = _implementation
