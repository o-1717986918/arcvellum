"""Compatibility alias for the runtime task-program service."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".runtime.task_program", __package__)
