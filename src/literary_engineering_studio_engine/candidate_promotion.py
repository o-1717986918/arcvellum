"""Compatibility alias for scene candidate promotion."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.promotion.candidate", __package__)
