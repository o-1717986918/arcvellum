"""Compatibility facade for :mod:`tasking.contract_audit`."""
from .tasking import contract_audit as _implementation

globals().update({name: getattr(_implementation, name) for name in dir(_implementation) if not name.startswith("__")})
