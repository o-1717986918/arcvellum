"""Compatibility alias for scene route gates."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.scene.gates", __package__)
