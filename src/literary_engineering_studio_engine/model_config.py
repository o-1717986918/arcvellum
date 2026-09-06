"""Compatibility alias for :mod:`.foundation.model_config`."""

import sys
import warnings

from .foundation import model_config as _implementation

warnings.warn(
    "literary_engineering_studio_engine.model_config is deprecated; import literary_engineering_studio_engine.foundation.model_config instead; removal is no earlier than 1.0.0",
    DeprecationWarning,
    stacklevel=2,
)
sys.modules[__name__] = _implementation
