"""Compatibility alias for :mod:`workflow.state`."""
import sys
import warnings
from .workflow import state as _implementation

warnings.warn(
    "literary_engineering_studio_engine.workflow_state is deprecated; import literary_engineering_studio_engine.workflow.state instead; removal is no earlier than 1.0.0",
    DeprecationWarning,
    stacklevel=2,
)
sys.modules[__name__] = _implementation
