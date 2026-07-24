"""Compatibility alias for the CLI-mediated task registry."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".tasking.registry", __package__)
