"""Private, nonce-bound desktop sidecar startup protocol.

This module owns the loopback binding policy and the ready-file handoff used
by the Tauri shell.  Keeping it outside the user-facing CLI parser gives the
desktop lifecycle a focused, independently testable boundary while preserving
the ``literary_engineering_studio.cli`` compatibility exports.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
from pathlib import Path

from .. import __version__


def is_loopback_host(host: str) -> bool:
    """Return whether ``host`` is a local-only bind address."""

    normalized = host.strip().lower()
    if normalized in {"localhost", "::1"}:
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def validate_serve_binding(host: str, api_token: str) -> None:
    """Reject non-local Studio APIs unless the caller configured a token."""

    if not is_loopback_host(host) and not api_token.strip():
        raise ValueError("refusing to bind Studio API beyond loopback without LES_API_TOKEN")


async def serve_with_ready_file(uvicorn, application, *, host: str, port: int, ready_file: Path) -> int:
    """Start Uvicorn and atomically publish the actual nonce-bound port."""

    ready_file = ready_file.expanduser().resolve()
    ready_file.parent.mkdir(parents=True, exist_ok=True)
    ready_file.unlink(missing_ok=True)
    server = uvicorn.Server(uvicorn.Config(application, host=host, port=port, log_level="info"))
    serve_task = asyncio.create_task(server.serve())
    try:
        deadline = asyncio.get_running_loop().time() + 45
        while not server.started and not serve_task.done() and asyncio.get_running_loop().time() < deadline:
            await asyncio.sleep(0.025)
        if not server.started:
            await serve_task
            raise RuntimeError("Studio API sidecar did not become ready")
        write_ready_file(ready_file, bound_port(server))
        await serve_task
        return 0
    finally:
        if not ready_file.exists() and serve_task.done() and not serve_task.cancelled():
            # An absent file intentionally means the sidecar never completed
            # its controlled startup contract.
            pass


def bound_port(server) -> int:
    """Read Uvicorn's OS-assigned listening port after startup."""

    for instance in getattr(server, "servers", []):
        for socket in getattr(instance, "sockets", []) or []:
            address = socket.getsockname()
            if isinstance(address, tuple) and len(address) >= 2:
                return int(address[1])
    raise RuntimeError("Studio API started without an observable bound port")


def write_ready_file(path: Path, port: int) -> None:
    """Atomically write the desktop handoff record after validation."""

    if not 1 <= int(port) <= 65535:
        raise ValueError(f"invalid Studio API port: {port}")
    payload = {
        "application_id": "arcvellum-studio",
        "protocol_version": "arcvellum-sidecar/v1",
        "version": __version__,
        "port": int(port),
        "startup_nonce": os.environ.get("LES_STARTUP_NONCE", "").strip(),
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)
