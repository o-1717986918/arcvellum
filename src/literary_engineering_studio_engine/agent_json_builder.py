"""Compatibility alias for Agent JSON candidate helpers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.agents.json_builder", __package__)
