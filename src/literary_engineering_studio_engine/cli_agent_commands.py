"""Compatibility alias for Engine Agent CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.agent", __package__)
