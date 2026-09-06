"""Compatibility alias for work-project initialization."""
from importlib import import_module
import sys
import warnings
warnings.warn(
    "literary_engineering_studio_engine.init_project is deprecated; import literary_engineering_studio_engine.projects.init instead; removal is no earlier than 1.0.0",
    DeprecationWarning,
    stacklevel=2,
)
sys.modules[__name__] = import_module(".projects.init", __package__)
