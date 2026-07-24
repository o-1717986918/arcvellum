"""Compatibility alias for style learning lab."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.lab", __package__)
