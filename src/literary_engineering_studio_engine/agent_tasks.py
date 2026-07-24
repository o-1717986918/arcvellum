"""Compatibility alias for task-sidecar writing."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".tasking.agent_tasks.writer", __package__)
