"""Compatibility alias for :mod:`workflow.state`."""
import sys
from .workflow import state as _implementation

sys.modules[__name__] = _implementation
