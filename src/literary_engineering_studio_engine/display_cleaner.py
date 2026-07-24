"""Compatibility alias for :mod:`.foundation.display_cleaner`."""

import sys

from .foundation import display_cleaner as _implementation

sys.modules[__name__] = _implementation
