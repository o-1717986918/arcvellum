"""Compatibility alias for :mod:`workflow.state_style`."""
import sys
from .workflow import state_style as _implementation

sys.modules[__name__] = _implementation
