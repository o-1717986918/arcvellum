"""Compatibility alias for route-audit evidence helpers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.evidence", __package__)
