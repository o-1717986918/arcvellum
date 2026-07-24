"""Compatibility alias for Engine scene CLI commands."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".command_line.commands.scene", __package__)
