"""Compatibility alias for compiled style constraints."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.compiler", __package__)
