"""Compatibility alias for :mod:`.observability.agent_observability`."""

import sys

from .observability import agent_observability as _implementation

sys.modules[__name__] = _implementation
