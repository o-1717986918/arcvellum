"""Compatibility alias for :mod:`workflow.state_scene`."""
import sys
from .workflow import state_scene as _implementation

sys.modules[__name__] = _implementation
