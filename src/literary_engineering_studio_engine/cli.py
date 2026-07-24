"""Compatibility and ``python -m`` entry point for Engine commands."""

from importlib import import_module
import sys

_implementation = import_module(".command_line.entry", __package__)
sys.modules[__name__] = _implementation

if __name__ == "__main__":
    raise SystemExit(_implementation.main())
