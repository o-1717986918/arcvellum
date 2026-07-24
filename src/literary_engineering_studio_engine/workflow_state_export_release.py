"""Compatibility alias for :mod:`workflow.state_export_release`."""
import sys
from .workflow import state_export_release as _implementation

sys.modules[__name__] = _implementation
