"""Compatibility alias for :mod:`.projections.whole_book_release`."""

import sys

from .projections import whole_book_release as _implementation

sys.modules[__name__] = _implementation
