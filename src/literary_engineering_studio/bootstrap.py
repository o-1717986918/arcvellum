"""Compatibility alias for :mod:`.application.bootstrap`."""

import sys

from .application import bootstrap as _implementation

sys.modules[__name__] = _implementation
