"""Compatibility alias for :mod:`.observability.runtime_events`."""

import sys

from .observability import runtime_events as _implementation

sys.modules[__name__] = _implementation
