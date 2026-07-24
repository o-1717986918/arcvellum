"""Compatibility alias for :mod:`workflow.state_longform`."""
import sys
from .workflow import state_longform as _implementation

sys.modules[__name__] = _implementation
