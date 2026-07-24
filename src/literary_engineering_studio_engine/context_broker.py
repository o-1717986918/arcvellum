"""Compatibility alias for scene context retrieval."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.context.broker", __package__)
