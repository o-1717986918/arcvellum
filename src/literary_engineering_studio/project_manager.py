"""Compatibility alias for :mod:`.application.project_manager`."""

import sys

from .application import project_manager as _implementation

sys.modules[__name__] = _implementation
