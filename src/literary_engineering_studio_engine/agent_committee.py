"""Compatibility alias for multi-reviewer committee support."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.review.committee", __package__)
