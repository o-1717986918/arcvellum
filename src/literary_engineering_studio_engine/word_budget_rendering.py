"""Compatibility facade for :mod:`literary.planning.rendering`."""
from .literary.planning import rendering as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
