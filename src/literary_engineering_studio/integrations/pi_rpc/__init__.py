"""Strict Pi coding-agent RPC integration primitives."""

from .framing import JsonlFramer, PiRpcProtocolError, encode_jsonl
from .process import PiRpcProcess, PiRpcProcessError

__all__ = [
    "JsonlFramer",
    "PiRpcProcess",
    "PiRpcProcessError",
    "PiRpcProtocolError",
    "encode_jsonl",
]
