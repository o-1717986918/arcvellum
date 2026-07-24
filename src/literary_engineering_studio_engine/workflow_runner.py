"""Compatibility alias for the diagnostic workflow runner."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".workflow.runner", __package__)
