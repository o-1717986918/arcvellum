"""Compatibility alias for :mod:`.advisor.advisor_snapshot`."""

import importlib
import sys

_implementation = importlib.import_module(".advisor.advisor_snapshot", __package__)

sys.modules[__name__] = _implementation
