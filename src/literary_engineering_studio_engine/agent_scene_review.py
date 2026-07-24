"""Compatibility alias for independent Agent scene review."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.review.scene_agent", __package__)
