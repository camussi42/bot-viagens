"""Autenticacao na API Infotravel.

POST /authenticate {username, password, client, agency}
  -> {accessToken, type: "Bearer", expire_seconds: 86400}

O token e opaco (nao e JWT). Cache com margem de seguranca e
renovacao automatica ao receber HTTP 401 (via ApiClient).
"""
from __future__ import annotations

import time
from typing import Any, Protocol

from .settings import InfotravelSettings
from .transport import HttpError, Transport


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...
    def set(self, key: str, value: str, ttl_seconds: int) -> None: ...


class MemoryCache:
    """Cache em memoria com expiracao (fallback quando nao ha Redis)."""

    def __init__(self, clock=time.time):
        self._data: dict = {}
        self._clock = clock

    def get(self, key: str) -> str | None:
        item = self._data.get(key)
        if not item:
            return None
        value, expires_at = item
        if self._clock() >= expires_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._data[key] = (value, self._clock() + max(ttl_seconds, 1))


class RedisCache:
    """Adaptador para um cliente redis compativel (redis-py). Import lazy."""

    def __init__(self, client: Any):
        self._client = client

    def get(self, key: str) -> str | None:
        value = self._client.get(key)
        if value is None:
            return None
        return value.decode("utf-8") if isinstance(value, bytes) else str(value)

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        self._client.set(key, value, ex=ttl_seconds)


class AuthManager:
    TOKEN_TTL_MARGIN = 300  # renova 5 min antes de expirar

    def __init__(self, settings: InfotravelSettings, transport: Transport | None = None,
                 cache: Cache | None = None):
        self.settings = settings
        self.transport = transport or Transport()
        self.cache = cache or MemoryCache()

    @property
    def _key(self) -> str:
        return f"infotravel:token:{self.settings.client}"

    def token(self, force: bool = False) -> str:
        if not force:
            cached = self.cache.get(self._key)
            if cached:
                return cached
        return self.refresh()

    def refresh(self) -> str:
        payload = {
            "username": self.settings.username,
            "password": self.settings.password,
            "client": self.settings.client,
            "agency": self.settings.agency,
        }
        data = self.transport.request(
            "POST", f"{self.settings.base_url}/authenticate", body=payload)
        token = (data or {}).get("accessToken", "")
        if not token:
            raise RuntimeError(f"Autenticacao Infotravel sem accessToken: {data!r}"[:300])
        try:
            ttl = int((data or {}).get("expire_seconds", 86400))
        except (TypeError, ValueError):
            ttl = 86400
        self.cache.set(self._key, token, ttl - self.TOKEN_TTL_MARGIN)
        return token


class ApiClient:
    """Chamadas autenticadas com retry transparente no 401."""

    def __init__(self, settings: InfotravelSettings, transport: Transport | None = None,
                 cache: Cache | None = None):
        self.settings = settings
        self.transport = transport or Transport()
        self.auth = AuthManager(settings, self.transport, cache)

    def call(self, method: str, path: str, *, params: dict | None = None,
             body: Any = None, timeout: float | None = None) -> Any:
        if not self.settings.configured:
            faltando = ", ".join(self.settings.missing())
            raise RuntimeError(
                f"Credenciais Infotravel ausentes: {faltando}. Ver docs/CREDENCIAIS.md")
        url = f"{self.settings.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.auth.token()}"}
        transport = self.transport if timeout is None else Transport(
            timeout=timeout, limiter=self.transport.limiter)
        try:
            return transport.request(method, url, headers=headers, params=params, body=body)
        except HttpError as exc:
            if exc.status == 401:  # token expirou no meio do caminho: renova 1x
                headers = {"Authorization": f"Bearer {self.auth.refresh()}"}
                return transport.request(method, url, headers=headers, params=params, body=body)
            raise
