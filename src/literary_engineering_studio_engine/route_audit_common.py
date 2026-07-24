"""Compatibility alias for shared route-audit helpers."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.common", __package__)
