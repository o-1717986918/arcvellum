"""Compatibility alias for :mod:`.foundation.model_config`."""

import sys

from .foundation import model_config as _implementation

sys.modules[__name__] = _implementation
