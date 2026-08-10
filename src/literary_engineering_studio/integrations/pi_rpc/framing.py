"""Strict UTF-8, LF-delimited JSON framing used by Pi RPC mode."""

from __future__ import annotations

import json
from typing import Any


class PiRpcProtocolError(RuntimeError):
    pass


def encode_jsonl(payload: dict[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


class JsonlFramer:
    def __init__(self) -> None:
        self._buffer = bytearray()

    def feed(self, chunk: bytes) -> tuple[dict[str, Any], ...]:
        self._buffer.extend(chunk)
        records: list[dict[str, Any]] = []
        while True:
            newline = self._buffer.find(b"\n")
            if newline < 0:
                break
            raw = bytes(self._buffer[:newline])
            del self._buffer[: newline + 1]
            if raw.endswith(b"\r"):
                raw = raw[:-1]
            if not raw:
                continue
            records.append(_decode_record(raw))
        return tuple(records)

    def finish(self) -> tuple[dict[str, Any], ...]:
        if not self._buffer:
            return ()
        raw = bytes(self._buffer)
        self._buffer.clear()
        if raw.endswith(b"\r"):
            raw = raw[:-1]
        return (_decode_record(raw),) if raw else ()


def _decode_record(raw: bytes) -> dict[str, Any]:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PiRpcProtocolError("Pi RPC JSONL must not contain a UTF-8 BOM")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PiRpcProtocolError(f"invalid Pi RPC JSONL record: {exc}") from exc
    if not isinstance(value, dict):
        raise PiRpcProtocolError("Pi RPC JSONL records must be objects")
    return value
