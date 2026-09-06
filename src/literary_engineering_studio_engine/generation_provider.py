"""Compatibility alias for provider-neutral prose generation."""
from importlib import import_module
import sys
import warnings
warnings.warn(
    "literary_engineering_studio_engine.generation_provider is deprecated; import literary_engineering_studio_engine.literary.scene.generation_provider instead; removal is no earlier than 1.0.0",
    DeprecationWarning,
    stacklevel=2,
)
sys.modules[__name__] = import_module(".literary.scene.generation_provider", __package__)
