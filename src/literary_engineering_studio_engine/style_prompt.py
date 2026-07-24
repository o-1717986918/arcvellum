"""Compatibility alias for mountable style prompts."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.prompt", __package__)
