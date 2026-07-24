"""Compatibility alias for the formal route catalog."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".routes.catalog", __package__)
