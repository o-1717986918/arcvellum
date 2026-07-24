"""Compatibility alias for deterministic review CI."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.review.ci", __package__)
