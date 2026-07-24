"""Compatibility alias for Engine asset CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.assets", __package__)
