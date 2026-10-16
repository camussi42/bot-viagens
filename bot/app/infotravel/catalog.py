"""Catalogo de pacotes (Search Engine): origin -> destination -> period.

Ordem obrigatoria: cada passo alimenta o seguinte. Pular etapa produz
o 400 enganoso do exceptionCode 1278 (§ errors.py).

GET /searchEngine/package/{tipo}/origin[?name=|iata=]
GET /searchEngine/package/{tipo}/destination?origin=&originType=
GET /searchEngine/package/{tipo}/period?origin=&originType=&destination=&destinationType=
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .auth import ApiClient

TIPOS_PACOTE = ("hotel", "hotel_flight", "flight_service", "hotel_bus",
                "service_bus", "dynamic", "multidestination")


@dataclass(frozen=True)
class Opcao:
    id: int
    nome: str
    tipo: str = ""   # "M" regiao | "A" aeroporto
    iata: str = ""


@dataclass
class Catalogo:
    origens: list = field(default_factory=list)
    destinos: list = field(default_factory=list)
    periodos: list = field(default_factory=list)


def _como_opcao(item: Any) -> Opcao | None:
    if not isinstance(item, dict):
        return None
    try:
        codigo = int(item.get("id", item.get("code", 0)) or 0)
    except (TypeError, ValueError):
        return None
    nome = str(item.get("name", item.get("nome", "")) or "").strip()
    if not codigo or not nome:
        return None
    return Opcao(id=codigo, nome=nome,
                 tipo=str(item.get("type", item.get("tipo", "")) or "").upper(),
                 iata=str(item.get("iata", "") or "").upper())


def _extrair_lista(resposta: Any, chaves: tuple) -> list:
    if isinstance(resposta, dict):
        for chave in chaves:
            valor = resposta.get(chave)
            if isinstance(valor, list):
                return [o for o in (_como_opcao(i) for i in valor) if o]
    if isinstance(resposta, list):
        return [o for o in (_como_opcao(i) for i in resposta) if o]
    return []


class CatalogClient:
    def __init__(self, api: ApiClient):
        self.api = api

    def _get(self, path: str, params: dict) -> Any:
        params = {k: v for k, v in params.items() if v not in (None, "")}
        return self.api.call("GET", path, params=params)

    def origens(self, tipo: str, termo: str = "", iata: str = "") -> list:
        """Sem termo: origens publicadas. Com name/iata: AMPLIA (soma aeroportos)."""
        if tipo not in TIPOS_PACOTE:
            raise ValueError(f"packageType invalido: {tipo!r}. Use um de {TIPOS_PACOTE}")
        params = {"language": "pt_BR"}
        if termo:
            params["name"] = termo
        if iata:
            params["iata"] = iata.upper()
        resp = self._get(f"/searchEngine/package/{tipo}/origin", params)
        return _extrair_lista(resp, ("origins", "origens", "items", "data"))

    def destinos(self, tipo: str, origem: int, origem_tipo: str) -> list:
        resp = self._get(f"/searchEngine/package/{tipo}/destination",
                         {"origin": origem, "originType": origem_tipo.upper(),
                          "language": "pt_BR"})
        return _extrair_lista(resp, ("destinations", "destinos", "items", "data"))

    def periodos(self, tipo: str, origem: int, origem_tipo: str,
                 destino: int, destino_tipo: str) -> list:
        """Retorna [{'start': 'YYYY-MM-DD', 'ends': ['YYYY-MM-DD', ...]}]."""
        resp = self._get(f"/searchEngine/package/{tipo}/period",
                         {"origin": origem, "originType": origem_tipo.upper(),
                          "destination": destino, "destinationType": destino_tipo.upper(),
                          "language": "pt_BR"})
        periodos = []
        itens = resp.get("periods", resp.get("periodos", [])) if isinstance(resp, dict) else resp
        for item in itens or []:
            if isinstance(item, dict) and item.get("start"):
                periodos.append({"start": str(item["start"])[:10],
                                 "ends": [str(e)[:10] for e in item.get("endDates", []) or []]})
        return periodos

    @staticmethod
    def achar_por_nome(opcoes: list, texto: str) -> Opcao | None:
        """Casamento exato (case-insensitive) primeiro; depois 'contem'.

        IMPORTANTE: nunca usar id de municipio aqui. Como as opcoes ja vem do
        catalogo de pacotes (ids de regiao/aeroporto), o risco 23500-vs-2802
        desaparece por construcao.
        """
        alvo = (texto or "").strip().lower()
        if not alvo:
            return None
        for opc in opcoes:
            if opc.nome.lower() == alvo or opc.nome.lower().split(",")[0].strip() == alvo:
                return opc
        candidatos = [o for o in opcoes if alvo in o.nome.lower()]
        return candidatos[0] if len(candidatos) == 1 else None
