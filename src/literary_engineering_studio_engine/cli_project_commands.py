"""Compatibility alias for Engine project CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.projects", __package__)
