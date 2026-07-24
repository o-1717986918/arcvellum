"""Compatibility alias for Agent provider execution."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.agents.provider", __package__)
