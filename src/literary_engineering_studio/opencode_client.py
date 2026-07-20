"""Narrow typed client for the OpenCode headless server."""

from __future__ import annotations

from dataclasses import dataclass
import base64
import json
from pathlib import Path
import socket
import threading
from typing import Any, Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class OpenCodeEndpoint:
    base_url: str
    username: str
    password: str
    directory: Path


class OpenCodeClient:
    def __init__(self, endpoint: OpenCodeEndpoint, *, timeout: float = 20.0):
        self.endpoint = endpoint
        self.timeout = timeout

    def health(self) -> dict[str, Any]:
        return self._json("GET", "/global/health", include_directory=False)

    def providers(self) -> dict[str, Any]:
        return self._json("GET", "/provider")

    def provider_auth_methods(self) -> dict[str, Any]:
        return self._json("GET", "/provider/auth")

    def set_auth(self, provider_id: str, credentials: dict[str, Any]) -> bool:
        result = self._json("PUT", f"/auth/{quote(provider_id, safe='')}", credentials)
        return bool(result)

    def delete_auth(self, provider_id: str) -> bool:
        return bool(self._json("DELETE", f"/auth/{quote(provider_id, safe='')}"))

    def create_session(self, title: str) -> dict[str, Any]:
        return self._json("POST", "/session", {"title": title})

    def session_status(self) -> dict[str, Any]:
        return self._json("GET", "/session/status")

    def prompt_async(self, session_id: str, *, text: str, model: str, agent: str) -> None:
        provider_id, model_id = split_model(model)
        body = {
            "agent": agent,
            "model": {"providerID": provider_id, "modelID": model_id},
            "parts": [{"type": "text", "text": text}],
        }
        self._request("POST", f"/session/{quote(session_id, safe='')}/prompt_async", body)

    def messages(self, session_id: str, *, limit: int = 100) -> list[dict[str, Any]]:
        payload = self._json(
            "GET",
            f"/session/{quote(session_id, safe='')}/message",
            query={"limit": max(1, min(1000, int(limit)))},
        )
        return payload if isinstance(payload, list) else []

    def diff(self, session_id: str) -> list[dict[str, Any]]:
        payload = self._json("GET", f"/session/{quote(session_id, safe='')}/diff")
        return payload if isinstance(payload, list) else []

    def abort(self, session_id: str) -> bool:
        return bool(self._json("POST", f"/session/{quote(session_id, safe='')}/abort", {}))

    def dispose(self) -> bool:
        return bool(self._json("POST", "/instance/dispose", {}))

    def events(self, stop: threading.Event) -> Iterator[dict[str, Any]]:
        request = self._build_request("GET", "/event")
        try:
            with urlopen(request, timeout=60) as response:
                data_lines: list[str] = []
                while not stop.is_set():
                    raw = response.readline()
                    if not raw:
                        break
                    line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                    if not line:
                        if data_lines:
                            text = "\n".join(data_lines)
                            data_lines.clear()
                            try:
                                payload = json.loads(text)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(payload, dict):
                                yield payload
                        continue
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
        except (OSError, HTTPError, URLError, socket.timeout):
            if not stop.is_set():
                raise

    def _json(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
        include_directory: bool = True,
    ) -> Any:
        response = self._request(method, path, body, query=query, include_directory=include_directory)
        if not response:
            return None
        try:
            return json.loads(response.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"OpenCode returned invalid JSON for {path}") from exc

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
        include_directory: bool = True,
    ) -> bytes:
        request = self._build_request(method, path, body, query=query, include_directory=include_directory)
        try:
            with urlopen(request, timeout=self.timeout) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"OpenCode API {method} {path} failed with {exc.code}: {detail[:1000]}") from exc
        except (OSError, URLError) as exc:
            raise RuntimeError(f"OpenCode API {method} {path} failed: {exc}") from exc

    def _build_request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        query: dict[str, Any] | None = None,
        include_directory: bool = True,
    ) -> Request:
        values = dict(query or {})
        if include_directory:
            values.setdefault("directory", str(self.endpoint.directory))
        url = self.endpoint.base_url.rstrip("/") + path
        if values:
            url += "?" + urlencode(values)
        token = base64.b64encode(f"{self.endpoint.username}:{self.endpoint.password}".encode("utf-8")).decode("ascii")
        headers = {"Accept": "application/json", "Authorization": f"Basic {token}"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        return Request(url, data=data, headers=headers, method=method)


def split_model(value: str) -> tuple[str, str]:
    normalized = str(value or "").strip()
    if "/" not in normalized:
        raise ValueError("OpenCode model must use provider/model-id format")
    provider, model = normalized.split("/", 1)
    if not provider or not model:
        raise ValueError("OpenCode model must use provider/model-id format")
    return provider, model
