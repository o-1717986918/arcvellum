"""Compatibility alias for platform-agent task writers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".prompting.platform_tasks", __package__)
