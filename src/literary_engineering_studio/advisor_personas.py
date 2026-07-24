"""Compatibility alias for :mod:`.advisor.advisor_personas`."""

import importlib
import sys

_implementation = importlib.import_module(".advisor.advisor_personas", __package__)

sys.modules[__name__] = _implementation
