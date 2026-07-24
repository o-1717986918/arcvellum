"""Compatibility alias for Engine CLI parser."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.parser", __package__)
