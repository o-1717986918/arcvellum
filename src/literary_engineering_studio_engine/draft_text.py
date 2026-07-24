"""Compatibility alias for :mod:`.foundation.draft_text`."""

import sys

from .foundation import draft_text as _implementation

sys.modules[__name__] = _implementation
