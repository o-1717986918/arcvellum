"""Compatibility alias for anti-AI-style deterministic lint."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.style.anti_ai", __package__)
