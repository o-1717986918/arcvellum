"""Compatibility alias for work-project initialization."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".projects.init", __package__)
