"""Compatibility alias for style evaluation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.evaluator", __package__)
