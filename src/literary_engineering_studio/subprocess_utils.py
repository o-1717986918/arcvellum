"""Compatibility alias for :mod:`.runtime.subprocess_utils`."""

import sys

from .runtime import subprocess_utils as _implementation

sys.modules[__name__] = _implementation
