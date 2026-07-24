"""Compatibility alias for longform quality audit."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.review.longform_audit", __package__)
