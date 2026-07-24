"""Compatibility alias for style-prompt Agent tasks."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.prompt_agent", __package__)
