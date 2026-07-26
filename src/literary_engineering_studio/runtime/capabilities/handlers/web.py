"""Allow-listed, no-redirect research retrieval."""

from __future__ import annotations

from html.parser import HTMLParser
import re
from typing import Any
import urllib.error
import urllib.request

from ..context import CapabilityContext
from ..contracts import HandlerOutput


MAX_WEB_BYTES = 256 * 1024


def research_web(context: CapabilityContext, arguments: dict[str, Any]) -> HandlerOutput:
    url = str(arguments.get("url") or "").strip()
    max_bytes = min(MAX_WEB_BYTES, _bounded_int(arguments.get("max_bytes"), 64 * 1024))
    fetcher = context.web_fetcher or _fetch_no_redirect
    final_url, content_type, text = fetcher(url, max_bytes=max_bytes)
    _validate_final_domain(final_url, context.manifest.network_domains)
    if "html" in content_type.lower():
        parser = _VisibleTextParser()
        parser.feed(text)
        text = parser.text()
    text = re.sub(r"\s+", " ", text).strip()
    return HandlerOutput(
        "web research candidate retrieved; it is not Canon evidence until reviewed",
        {
            "url": final_url,
            "content_type": content_type,
            "research_candidate": text,
            "canonical_status": "unverified-research-candidate",
        },
    )


def _fetch_no_redirect(url: str, *, max_bytes: int) -> tuple[str, str, str]:
    opener = urllib.request.build_opener(_NoRedirect())
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "ArcVellum-CapabilityBroker/1.0", "Accept": "text/html,text/plain,application/json"},
    )
    try:
        with opener.open(request, timeout=12) as response:
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise ValueError(f"research.web response exceeds {max_bytes} bytes")
            content_type = response.headers.get_content_type()
            charset = response.headers.get_content_charset() or "utf-8"
            return response.geturl(), content_type, body.decode(charset, errors="replace")
    except urllib.error.HTTPError as exc:
        if 300 <= exc.code < 400:
            raise ValueError("research.web redirects are not followed") from exc
        raise


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._hidden_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._hidden_depth:
            self._hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._hidden_depth and data.strip():
            self._parts.append(data.strip())

    def text(self) -> str:
        return " ".join(self._parts)


def _validate_final_domain(url: str, domains: tuple[str, ...]) -> None:
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    if not any(host == domain or host.endswith("." + domain) for domain in domains):
        raise ValueError(f"research.web final domain is not allow-listed: {host}")


def _bounded_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1_024, parsed)
