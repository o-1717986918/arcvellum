"""Compatibility facade for :mod:`literary.planning.contracts`."""
from .literary.planning import contracts as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
