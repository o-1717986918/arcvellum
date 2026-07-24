"""Compatibility alias for macro and chapter rhythm planning."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.planning.rhythm_plan", __package__)
