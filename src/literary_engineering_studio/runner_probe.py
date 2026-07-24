"""Compatibility alias for :mod:`.integrations.opencode.runner_probe`."""

import sys

from .integrations.opencode import runner_probe as _implementation

sys.modules[__name__] = _implementation
