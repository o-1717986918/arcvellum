"""Compatibility facade for :mod:`literary.planning.allocation`."""
from .literary.planning import allocation as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
