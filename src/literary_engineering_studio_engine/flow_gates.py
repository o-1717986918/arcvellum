"""Compatibility alias for formal task gates."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".tasking.gates", __package__)
