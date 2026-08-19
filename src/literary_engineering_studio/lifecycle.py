"""Compatibility alias for the infrastructure-owned legacy lifecycle."""

import sys

from .infrastructure import legacy_lifecycle as _implementation

sys.modules[__name__] = _implementation
