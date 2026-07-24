"""Compatibility facade for :mod:`tasking.lifecycle`."""
from .tasking import lifecycle as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
