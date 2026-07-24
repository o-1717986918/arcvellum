"""Compatibility alias for deterministic demo project creation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".projects.demo", __package__)
