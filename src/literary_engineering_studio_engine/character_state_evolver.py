"""Compatibility alias for character state evolution."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.state.evolver", __package__)
