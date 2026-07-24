"""Compatibility alias for release fingerprints."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.export.fingerprint", __package__)
