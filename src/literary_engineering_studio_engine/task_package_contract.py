"""Compatibility facade for :mod:`tasking.package_contract`."""
from .tasking import package_contract as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
