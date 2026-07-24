"""Compatibility alias for Engine formal CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.formal", __package__)
