"""Compatibility alias for :mod:`.foundation.atomic_io`."""

import sys

from .foundation import atomic_io as _implementation

sys.modules[__name__] = _implementation
