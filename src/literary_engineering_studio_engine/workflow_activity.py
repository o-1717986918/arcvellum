"""Compatibility alias for :mod:`workflow.activity`."""
import sys
from .workflow import activity as _implementation

sys.modules[__name__] = _implementation
