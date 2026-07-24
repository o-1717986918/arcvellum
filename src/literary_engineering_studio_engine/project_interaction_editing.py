"""Compatibility alias for project interaction edits."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".projections.interaction.editing", __package__)
