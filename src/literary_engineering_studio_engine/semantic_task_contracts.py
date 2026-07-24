"""Compatibility facade for :mod:`tasking.semantic_contracts`."""
from .tasking import semantic_contracts as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
