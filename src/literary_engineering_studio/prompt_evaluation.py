"""Compatibility alias for automation prompt evaluation."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".automation.prompt_evaluation", __package__)
