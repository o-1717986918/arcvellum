"""Compatibility alias for scene prompt-pack assembly."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.pack", __package__)
