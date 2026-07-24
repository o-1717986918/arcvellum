"""Compatibility facade for :mod:`projections.library.continuity`."""
from .projections.library import continuity as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
