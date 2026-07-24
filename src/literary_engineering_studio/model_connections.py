"""Compatibility alias for :mod:`.integrations.model_connections`."""

import sys

from .integrations import model_connections as _implementation

sys.modules[__name__] = _implementation
