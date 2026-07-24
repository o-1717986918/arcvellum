"""Compatibility alias for :mod:`.foundation.resources`."""

import sys

from .foundation import resources as _implementation

sys.modules[__name__] = _implementation
