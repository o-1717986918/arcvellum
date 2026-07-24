"""Compatibility alias for the runtime worker supervisor."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".runtime.supervisor", __package__)
