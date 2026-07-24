"""Compatibility facade for :mod:`literary.planning.inventory`."""
from .literary.planning import inventory as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
