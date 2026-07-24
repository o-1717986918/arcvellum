"""Compatibility alias for Engine longform CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.longform", __package__)
