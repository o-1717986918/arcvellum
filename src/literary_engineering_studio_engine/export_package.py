"""Compatibility alias for manuscript export packaging."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.export.package", __package__)
