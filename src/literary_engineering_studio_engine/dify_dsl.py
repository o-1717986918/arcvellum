"""Compatibility alias for :mod:`.foundation.dify_dsl`."""

import sys

from .foundation import dify_dsl as _implementation

sys.modules[__name__] = _implementation
