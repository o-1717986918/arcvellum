"""Compatibility alias for Agent structured-output schemas."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.agents.schema", __package__)
