"""Compatibility alias for :mod:`.integrations.opencode.opencode_profiles`."""

import sys

from .integrations.opencode import opencode_profiles as _implementation

sys.modules[__name__] = _implementation
