"""Compatibility alias for :mod:`.application.project_progress`."""

import sys

from .application import project_progress as _implementation

sys.modules[__name__] = _implementation
