"""Compatibility alias for longform plan materialization."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.planning.materializer", __package__)
