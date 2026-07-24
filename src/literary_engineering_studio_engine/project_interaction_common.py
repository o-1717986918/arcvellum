"""Compatibility alias for project interaction helpers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".projections.interaction.common", __package__)
