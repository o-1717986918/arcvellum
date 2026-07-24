"""Compatibility alias for :mod:`workflow.state_assets`."""
import sys
from .workflow import state_assets as _implementation

sys.modules[__name__] = _implementation
