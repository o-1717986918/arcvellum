"""Compatibility alias for orchestration blueprint rendering."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".tasking.orchestration", __package__)
