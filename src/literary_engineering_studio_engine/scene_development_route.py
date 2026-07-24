"""Compatibility alias for the formal scene-development route."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.scene.definition", __package__)
