"""Compatibility alias for static platform blueprint rendering."""
from importlib import import_module
import sys

sys.modules[__name__] = import_module(".platforms.orchestration_blueprint", __package__)
