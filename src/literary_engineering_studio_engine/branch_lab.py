"""Compatibility alias for branch simulation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.branching.lab", __package__)
