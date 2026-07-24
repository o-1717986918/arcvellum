"""Compatibility facade for :mod:`literary.planning.common`."""
from .literary.planning import common as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
