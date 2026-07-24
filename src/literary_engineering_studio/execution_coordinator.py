"""Compatibility alias for :mod:`.runtime.execution_coordinator`."""

import sys

from .runtime import execution_coordinator as _implementation

sys.modules[__name__] = _implementation
