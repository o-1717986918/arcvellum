"""Compatibility alias for Engine CLI policy."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.policy", __package__)
