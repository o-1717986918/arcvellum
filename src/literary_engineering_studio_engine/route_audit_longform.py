"""Compatibility alias for longform route-audit gates."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".workflow.audit.longform", __package__)
