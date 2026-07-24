"""Compatibility alias for the runtime Agent Worker."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".runtime.worker", __package__)
