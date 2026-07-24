"""Compatibility alias for :mod:`.integrations.opencode.opencode_client`."""

import sys

from .integrations.opencode import opencode_client as _implementation

sys.modules[__name__] = _implementation
