"""Compatibility facade for :mod:`projections.library.common`."""
from .projections.library import common as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
