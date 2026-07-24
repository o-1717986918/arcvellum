"""Compatibility alias for scene draft preparation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.composition.draft", __package__)
