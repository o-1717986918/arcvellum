"""Compatibility alias for asset route definition."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.assets.definition", __package__)
