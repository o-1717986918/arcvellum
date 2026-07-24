"""Compatibility alias for Engine legacy CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.legacy", __package__)
