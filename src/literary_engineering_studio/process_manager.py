"""Compatibility alias for :mod:`.runtime.process_manager`."""

import sys

from .runtime import process_manager as _implementation

sys.modules[__name__] = _implementation
