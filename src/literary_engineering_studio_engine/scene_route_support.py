"""Compatibility alias for scene route support helpers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.scene.support", __package__)
