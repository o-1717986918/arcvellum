"""Compatibility alias for Canon lint."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.canon.lint", __package__)
