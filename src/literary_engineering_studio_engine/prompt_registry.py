"""Compatibility alias for prompt asset registry."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.registry", __package__)
