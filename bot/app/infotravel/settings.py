"""Configuracao do cliente Infotravel lida de variaveis de ambiente.

Credenciais (username/password/client/agency + dominio) sao fornecidas
pela Infotera via menu de suporte. Ver docs/CREDENCIAIS.md.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_AGENCY = "2"


@dataclass(frozen=True)
class InfotravelSettings:
    domain: str = ""
    username: str = ""
    password: str = ""
    client: str = ""
    agency: str = DEFAULT_AGENCY
    env: str = "homologacao"

    @property
    def base_url(self) -> str:
        return f"https://{self.domain.strip()}/infotravel/api/v1"

    @property
    def configured(self) -> bool:
        return not self.missing()

    def missing(self) -> list:
        nomes = {
            "domain": "INFOTRAVEL_DOMAIN",
            "username": "INFOTRAVEL_USERNAME",
            "password": "INFOTRAVEL_PASSWORD",
            "client": "INFOTRAVEL_CLIENT",
            "agency": "INFOTRAVEL_AGENCY",
        }
        return [env for attr, env in nomes.items() if not getattr(self, attr)]


def from_env(get=os.environ.get) -> InfotravelSettings:
    return InfotravelSettings(
        domain=(get("INFOTRAVEL_DOMAIN") or "").strip(),
        username=(get("INFOTRAVEL_USERNAME") or "").strip(),
        password=get("INFOTRAVEL_PASSWORD") or "",
        client=(get("INFOTRAVEL_CLIENT") or "").strip(),
        agency=(get("INFOTRAVEL_AGENCY") or DEFAULT_AGENCY).strip(),
        env=(get("INFOTRAVEL_ENV") or "homologacao").strip().lower(),
    )
