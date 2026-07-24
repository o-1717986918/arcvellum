"""Compatibility alias for :mod:`.advisor.advisor_inbox`."""

import importlib
import sys

_implementation = importlib.import_module(".advisor.advisor_inbox", __package__)

sys.modules[__name__] = _implementation
