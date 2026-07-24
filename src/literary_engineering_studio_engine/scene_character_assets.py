"""Compatibility alias for scene character asset coordination."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.state.character_assets", __package__)
