"""Compatibility alias for export-and-release route definition."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.export.definition", __package__)
