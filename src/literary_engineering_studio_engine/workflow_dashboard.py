"""Compatibility alias for :mod:`workflow.dashboard`."""
import sys
from .workflow import dashboard as _implementation

sys.modules[__name__] = _implementation
