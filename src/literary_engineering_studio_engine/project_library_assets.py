"""Compatibility facade for :mod:`projections.library.assets`."""
from .projections.library import assets as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
