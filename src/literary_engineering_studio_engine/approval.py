"""Compatibility alias for tasking approval records."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".tasking.approval", __package__)
