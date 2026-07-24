"""Compatibility alias for asset context assembly."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.context", __package__)
