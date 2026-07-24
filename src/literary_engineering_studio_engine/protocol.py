"""Compatibility alias for formal operating protocol rendering."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".tasking.protocol", __package__)
