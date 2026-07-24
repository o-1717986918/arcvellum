"""Compatibility alias for :mod:`.integrations.opencode.opencode_binary`."""

import sys

from .integrations.opencode import opencode_binary as _implementation

sys.modules[__name__] = _implementation
