"""Compatibility alias for scene route task blueprints."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.scene.blueprints", __package__)
