"""Compatibility alias for :mod:`.observability.agent_session_tracking`."""

import sys

from .observability import agent_session_tracking as _implementation

sys.modules[__name__] = _implementation
