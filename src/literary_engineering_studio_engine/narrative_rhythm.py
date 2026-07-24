"""Compatibility alias for scene narrative rhythm contracts."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.planning.narrative_rhythm", __package__)
