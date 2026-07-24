"""Compatibility alias for workflow contract validation."""
from importlib import import_module
import sys
sys.modules[__name__] = import_module(".tasking.workflow_contract", __package__)
