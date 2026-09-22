"""Smoke-test an isolated installed sidecar against a read-only Orrery request."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _await_ready(path: Path, process: subprocess.Popen[bytes]) -> dict[str, object]:
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"installed sidecar exited before readiness: {process.returncode}")
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            else:
                if isinstance(payload, dict):
                    return payload
        time.sleep(0.25)
    raise TimeoutError("installed sidecar did not publish readiness within 45 seconds")


def _get_json(url: str, token: str) -> tuple[dict[str, object], object]:
    request = Request(
        url,
        headers={"Authorization": f"Bearer {token}", "Origin": "http://tauri.localhost"},
    )
    with urlopen(request, timeout=30) as response:
        body = json.load(response)
        if not isinstance(body, dict):
            raise RuntimeError("sidecar returned a non-object JSON body")
        return body, response.headers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args()
    executable = args.installed.resolve() / "literary-engineering-studio-sidecar.exe"
    project = args.project.resolve()
    if not executable.is_file() or not (project / "project.yaml").is_file():
        parser.error("installed sidecar or project.yaml is missing")

    with tempfile.TemporaryDirectory(prefix="arcvellum-release-smoke-") as temporary:
        isolated = Path(temporary)
        ready = isolated / "ready.json"
        token = secrets.token_urlsafe(32)
        nonce = secrets.token_hex(16)
        environment = os.environ.copy()
        environment.update(
            LES_API_TOKEN=token,
            LES_STARTUP_NONCE=nonce,
            LES_CONFIG_PATH=str(isolated / "config.json"),
            LES_DATA_ROOT=str(isolated / "data"),
            LES_PROJECTS_ROOT=str(isolated / "projects"),
        )
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        process = subprocess.Popen(
            [str(executable), "serve", "--host", "127.0.0.1", "--port", "0", "--ready-file", str(ready)],
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        try:
            handoff = _await_ready(ready, process)
            if handoff.get("version") != args.version or handoff.get("startup_nonce") != nonce:
                raise RuntimeError("sidecar readiness version or nonce mismatch")
            port = handoff.get("port")
            if not isinstance(port, int) or not 1 <= port <= 65535:
                raise RuntimeError("sidecar readiness has no valid port")
            base = f"http://127.0.0.1:{port}"
            health, _ = _get_json(f"{base}/health", token)
            if health.get("ok") is not True or health.get("version") != args.version:
                raise RuntimeError("installed sidecar health check failed")
            projection, headers = _get_json(
                f"{base}/narrative/projection/v4?{urlencode({'project_root': str(project)})}",
                token,
            )
            if projection.get("schema") != "arcvellum/narrative-projection/v4":
                raise RuntimeError("installed sidecar did not return the Orrery v4 projection")
            if headers.get("Access-Control-Allow-Origin") != "http://tauri.localhost":
                raise RuntimeError("installed sidecar omitted the Tauri CORS origin")
            if headers.get("Access-Control-Allow-Credentials") != "true":
                raise RuntimeError("installed sidecar omitted credentialed CORS")
            print(json.dumps({
                "version": handoff["version"],
                "health": "ok",
                "orrery_schema": projection["schema"],
                "nodes": len(projection.get("nodes") or []),
                "edges": len(projection.get("edges") or []),
                "tauri_cors": True,
            }, ensure_ascii=False))
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
