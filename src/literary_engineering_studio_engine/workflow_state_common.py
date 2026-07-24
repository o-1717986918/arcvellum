"""Compatibility alias for :mod:`workflow.state_common`."""
import sys
from .workflow import state_common as _implementation

sys.modules[__name__] = _implementation
