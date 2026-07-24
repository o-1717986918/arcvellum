"""Compatibility alias for scene composition."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.composition.composer", __package__)
