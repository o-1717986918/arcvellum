"""Compatibility alias for scene context packet generation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.context.packet", __package__)
