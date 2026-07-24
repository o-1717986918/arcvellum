"""Compatibility alias for chapter publication."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.export.publish", __package__)
