"""Compatibility alias for :mod:`.integrations.opencode.opencode_server`."""

import sys

from .integrations.opencode import opencode_server as _implementation

sys.modules[__name__] = _implementation
