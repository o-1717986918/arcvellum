"""Compatibility alias for style-engineering route definition."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.style.definition", __package__)
