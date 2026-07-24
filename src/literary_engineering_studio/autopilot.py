"""Compatibility alias for the automation controller."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".automation.controller", __package__)
