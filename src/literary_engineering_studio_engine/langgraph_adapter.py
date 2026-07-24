"""Compatibility alias for :mod:`.foundation.langgraph_adapter`."""

import sys

from .foundation import langgraph_adapter as _implementation

sys.modules[__name__] = _implementation
