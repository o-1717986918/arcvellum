"""Compatibility facade for :mod:`literary.planning.service`."""
from .literary.planning import service as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
