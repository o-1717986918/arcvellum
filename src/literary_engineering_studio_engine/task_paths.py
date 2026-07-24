"""Compatibility facade for :mod:`tasking.paths`."""
from .tasking import paths as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
