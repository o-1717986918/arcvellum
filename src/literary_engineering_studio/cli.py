"""Compatibility and ``python -m`` entry point for Studio commands."""

from importlib import import_module
import sys

_implementation = import_module(".application.cli", __package__)
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
