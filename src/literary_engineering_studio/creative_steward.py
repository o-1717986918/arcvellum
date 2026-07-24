"""Compatibility alias for :mod:`.advisor.creative_steward`."""

import importlib
import sys

_implementation = importlib.import_module(".advisor.creative_steward", __package__)

sys.modules[__name__] = _implementation
