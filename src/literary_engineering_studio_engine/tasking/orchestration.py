"""Compatibility facade for the historical platform blueprint module."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(
    "..platforms.orchestration_blueprint",
    __package__,
)
