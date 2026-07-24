"""Compatibility alias for export route-audit gates."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.export", __package__)
