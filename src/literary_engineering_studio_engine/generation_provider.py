"""Compatibility alias for provider-neutral prose generation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.scene.generation_provider", __package__)
