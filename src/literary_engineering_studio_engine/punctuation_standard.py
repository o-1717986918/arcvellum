"""Compatibility alias for punctuation standards."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.punctuation", __package__)
