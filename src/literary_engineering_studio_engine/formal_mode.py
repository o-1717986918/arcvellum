"""Compatibility alias for formal-mode safety helpers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.formal_mode", __package__)
