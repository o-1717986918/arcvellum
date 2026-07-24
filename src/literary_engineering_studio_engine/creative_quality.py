"""Compatibility alias for deterministic creative-quality checks."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.review.creative_quality", __package__)
