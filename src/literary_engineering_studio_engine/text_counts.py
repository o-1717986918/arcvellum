"""Compatibility alias for :mod:`.foundation.text_counts`."""

import sys

from .foundation import text_counts as _implementation

sys.modules[__name__] = _implementation
