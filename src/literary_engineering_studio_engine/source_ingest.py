"""Compatibility alias for source-work ingestion."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".projects.source_ingest", __package__)
