"""Compatibility alias for Engine legacy CLI commands."""
from importlib import import_module
import sys
import warnings
warnings.warn(
    "literary_engineering_studio_engine.cli_legacy_commands is deprecated; import literary_engineering_studio_engine.command_line.commands.legacy instead; removal is no earlier than 1.0.0",
    DeprecationWarning,
    stacklevel=2,
)
sys.modules[__name__] = import_module(".command_line.commands.legacy", __package__)
