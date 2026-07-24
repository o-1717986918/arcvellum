"""Compatibility alias for story architecture contracts."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.continuity.architecture", __package__)
