"""Compatibility alias for continuity ledger."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.continuity.ledger", __package__)
