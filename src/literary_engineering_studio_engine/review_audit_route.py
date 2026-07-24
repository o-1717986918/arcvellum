"""Compatibility alias for review-and-audit route definition."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.review.definition", __package__)
