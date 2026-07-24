"""Compatibility alias for :mod:`.integrations.opencode.opencode_runtime_pool`."""

import sys

from .integrations.opencode import opencode_runtime_pool as _implementation

sys.modules[__name__] = _implementation
