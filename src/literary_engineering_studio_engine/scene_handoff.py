"""Compatibility alias for scene handoff contracts."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.context.handoff", __package__)
