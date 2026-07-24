"""Compatibility alias for chapter planning pipeline."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.planning.chapter_pipeline", __package__)
