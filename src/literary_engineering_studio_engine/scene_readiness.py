"""Compatibility alias for scene readiness gates."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.promotion.readiness", __package__)
