"""Compatibility alias for Agent provider execution."""
from importlib import import_module
import sys
import warnings
warnings.warn(
    "literary_engineering_studio_engine.agent_provider is deprecated; import literary_engineering_studio_engine.prompting.agents.provider instead; removal is no earlier than 1.0.0",
    DeprecationWarning,
    stacklevel=2,
)
sys.modules[__name__] = import_module(".prompting.agents.provider", __package__)
