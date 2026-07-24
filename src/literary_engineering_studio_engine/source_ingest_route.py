"""Compatibility alias for source-ingest route definition."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".routes.source_ingest.definition", __package__)
