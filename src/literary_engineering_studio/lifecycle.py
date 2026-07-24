"""Compatibility alias for :mod:`.application.lifecycle`."""

import sys

from .application import lifecycle as _implementation

sys.modules[__name__] = _implementation
