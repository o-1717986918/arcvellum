"""Compatibility alias for scene revision planning."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.promotion.revision", __package__)
