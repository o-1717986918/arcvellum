"""Compatibility alias for task-sidecar rendering."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".tasking.agent_tasks.rendering", __package__)
