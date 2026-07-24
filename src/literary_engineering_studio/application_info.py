"""Compatibility alias for :mod:`.application.application_info`."""

import sys

from .application import application_info as _implementation

sys.modules[__name__] = _implementation
