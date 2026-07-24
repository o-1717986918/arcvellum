"""Compatibility alias for :mod:`.foundation.knowledge_store`."""

import sys

from .foundation import knowledge_store as _implementation

sys.modules[__name__] = _implementation
