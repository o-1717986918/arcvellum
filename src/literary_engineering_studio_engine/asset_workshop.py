"""Compatibility alias for candidate asset workshop."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.workshop", __package__)
