"""Compatibility alias for roleplay simulation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.roleplay.lab", __package__)
