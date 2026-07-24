"""Compatibility alias for :mod:`workflow.state_source_ingest`."""
import sys
from .workflow import state_source_ingest as _implementation

sys.modules[__name__] = _implementation
