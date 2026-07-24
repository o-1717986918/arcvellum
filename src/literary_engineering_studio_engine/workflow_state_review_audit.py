"""Compatibility alias for :mod:`workflow.state_review_audit`."""
import sys
from .workflow import state_review_audit as _implementation

sys.modules[__name__] = _implementation
