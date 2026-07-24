"""Compatibility alias for :mod:`.runtime.sandbox`."""

import sys

from .runtime import sandbox as _implementation

sys.modules[__name__] = _implementation
