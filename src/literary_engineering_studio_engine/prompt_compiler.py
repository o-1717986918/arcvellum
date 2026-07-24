"""Compatibility alias for prioritized prompt compilation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.compiler", __package__)
