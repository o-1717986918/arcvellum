"""Compatibility alias for :mod:`.foundation.memory_index`."""

import sys

from .foundation import memory_index as _implementation

sys.modules[__name__] = _implementation
