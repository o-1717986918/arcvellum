"""Compatibility alias for :mod:`.runtime.sidecar_protocol`."""

import sys

from .runtime import sidecar_protocol as _implementation

sys.modules[__name__] = _implementation
