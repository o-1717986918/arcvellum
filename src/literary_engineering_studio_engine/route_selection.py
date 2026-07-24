"""Compatibility alias for formal route work-item selection."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".routes.selection", __package__)
