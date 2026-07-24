"""Compatibility alias for project interaction choices."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".projections.interaction.choices", __package__)
