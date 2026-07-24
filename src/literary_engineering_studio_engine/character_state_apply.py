"""Compatibility alias for character state apply."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.state.apply", __package__)
