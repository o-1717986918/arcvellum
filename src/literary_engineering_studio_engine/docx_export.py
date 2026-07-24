"""Compatibility alias for DOCX export."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.export.docx", __package__)
