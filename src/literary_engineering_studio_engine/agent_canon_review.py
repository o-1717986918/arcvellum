"""Compatibility alias for Agent Canon review."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".literary.assets.canon.agent_review", __package__)
