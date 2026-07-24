"""Compatibility alias for workflow route-audit coordination."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.service", __package__)
