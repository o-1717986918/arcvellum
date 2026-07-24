"""Compatibility alias for durable JobStore persistence."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module(".persistence.job_store", __package__)
