"""Compatibility alias for style-prompt evaluation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.prompt_eval", __package__)
