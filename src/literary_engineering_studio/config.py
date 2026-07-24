"""Compatibility alias for :mod:`.application.config`."""

import sys

from .application import config as _implementation

sys.modules[__name__] = _implementation
