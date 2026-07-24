"""Compatibility alias for reader-experience contracts."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.review.reader_experience", __package__)
