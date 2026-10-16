"""Transporte HTTP sincrono (stdlib) com throttle de taxa.

O throttle protege o teto da API (~110 req/s por credencial).
"""
from __future__ import annotations

import json as _json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class HttpError(Exception):
    def __init__(self, status: int, body: Any, url: str):
        super().__init__(f"HTTP {status} em {url}: {body!r}"[:500])
        self.status = status
        self.body = body
        self.url = url


class RateLimiter:
    """Garante um intervalo minimo entre chamadas."""

    def __init__(self, min_interval: float = 0.02):
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._last = 0.0

    def wait(self) -> None:
        with self._lock:
            delta = time.monotonic() - self._last
            if delta < self.min_interval:
                time.sleep(self.min_interval - delta)
            self._last = time.monotonic()


class Transport:
    def __init__(self, timeout: float = 30.0, limiter: RateLimiter | None = None,
                 user_agent: str = "bot-viagens/0.1"):
        self.timeout = timeout
        self.limiter = limiter or RateLimiter()
        self.user_agent = user_agent

    def request(self, method: str, url: str, *, headers: dict | None = None,
                params: dict | None = None, body: Any = None) -> Any:
        if params:
            qs = urllib.parse.urlencode(params, doseq=True)
            url = f"{url}?{qs}" if "?" not in url else f"{url}&{qs}"
        data = None
        head = {"User-Agent": self.user_agent, "Accept": "application/json"}
        if headers:
            head.update(headers)
        if body is not None:
            data = _json.dumps(body, ensure_ascii=False).encode("utf-8")
            head["Content-Type"] = "application/json"
        self.limiter.wait()
        req = urllib.request.Request(url, data=data, headers=head, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:
            try:
                payload = exc.read().decode("utf-8", "replace")
            except Exception:
                payload = ""
            try:
                parsed: Any = _json.loads(payload) if payload else None
            except ValueError:
                parsed = payload
            raise HttpError(exc.code, parsed, url) from None
        if not raw:
            return None
        try:
            return _json.loads(raw)
        except ValueError:
            return raw
