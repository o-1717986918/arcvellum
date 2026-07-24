"""Compatibility alias for task-sidecar status and route-audit output."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.task_status", __package__)
