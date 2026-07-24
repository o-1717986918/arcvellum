"""Compatibility facade for :mod:`projections.library.service`."""
from .projections.library import service as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
