"""Compatibility alias for Canon candidate evolution and apply."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.canon.evolver", __package__)
