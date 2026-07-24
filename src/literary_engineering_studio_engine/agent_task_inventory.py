"""Compatibility alias for task-sidecar inventory."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".tasking.agent_tasks.inventory", __package__)
