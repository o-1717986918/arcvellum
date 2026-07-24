"""Compatibility alias for :mod:`.integrations.opencode.opencode_control`."""

import sys

from .integrations.opencode import opencode_control as _implementation

sys.modules[__name__] = _implementation
