"""Compatibility alias for the runtime-to-Engine CLI bridge."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".runtime.engine_bridge", __package__)
