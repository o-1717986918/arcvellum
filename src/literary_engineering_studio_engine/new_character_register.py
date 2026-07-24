"""Compatibility alias for new-character registration."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.state.new_character_register", __package__)
