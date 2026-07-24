"""Compatibility alias for review route-audit gates."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.review", __package__)
