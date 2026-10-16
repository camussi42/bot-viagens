"""Cotacao de pacote: avail/package (+ paginacao) e orcamento via checkRate/budget.

REGRA DE SEGURANCA: este modulo NUNCA chama POST /checkRate (cria pre-reserva,
status CREATION) nem POST /booking. Para preco firme usa POST /checkRate/budget
(mesmo corpo BookingRQ), que gera ORCAMENTO (status QUOTATION).
"""
from __future__ import annotations


def _params_cotacao(slots: dict) -> dict:
    return {
        "start": slots.get("data_inicio"),
        "end": slots.get("data_fim"),
        "occupancy": montar_occupancy(slots.get("ocupacao") or {}),
        "origin": (slots.get("origem") or {}).get("id"),
        "originType": (slots.get("origem") or {}).get("tipo"),
        "destination": (slots.get("destino") or {}).get("id"),
        "destinationType": (slots.get("destino") or {}).get("tipo"),
        "nationality": slots.get("nacionalidade") or "BR",
        "paged": True,
    }


def montar_occupancy(ocupacao: dict) -> list:
    """Formato: numberOfAdults[-idade1[,idade2]]; multi-quarto repete o parametro.

    Ex.: {'adultos': 2} -> ['2']; {'adultos': 2, 'criancas_idades': [9, 4]} -> ['2-9,4'].
    Todo quarto precisa de ao menos 1 adulto (validado).
    """
    quartos = ocupacao.get("quartos") or [{"adultos": ocupacao.get("adultos", 2),
                                           "criancas_idades": ocupacao.get("criancas_idades", [])}]
    if isinstance(quartos, dict):
        quartos = [quartos]
    params = []
    for quarto in quartos:
        adultos = int(quarto.get("adultos", 0) or 0)
        if adultos < 1:
            raise ValueError("Todo quarto precisa de ao menos 1 adulto.")
        idades = [str(int(i)) for i in (quarto.get("criancas_idades") or [])]
        params.append(f"{adultos}-{','.join(idades)}" if idades else str(adultos))
    return params


from typing import Any

from .auth import ApiClient
from .errors import ClientFacingError, client_message_for_avail_error
from .transport import HttpError


class QuoteClient:
    def __init__(self, api: ApiClient, supplier_timeout: int = 20):
        self.api = api
        self.supplier_timeout = supplier_timeout

    def disponibilidade(self, tipo: str, slots: dict, size: int = 5) -> dict:
        """GET /avail/package/{tipo} — pacotes + hoteis + voos + precos 'a partir de'."""
        params = _params_cotacao(slots)
        params.update({"size": size, "supplierTimeoutSeconds": self.supplier_timeout})
        params = {k: v for k, v in params.items() if v not in (None, "", [])}
        try:
            resp = self.api.call("GET", f"/avail/package/{tipo}", params=params)
        except HttpError as exc:
            raise ClientFacingError(client_message_for_avail_error(exc.status, exc.body)) from None
        return resp if isinstance(resp, dict) else {"packageAvails": []}

    def proxima_pagina(self, search_id: str, hotel_page: int = 1,
                       flight_page: int = 1, size: int = 5) -> dict:
        """POST /avail/package/search/{searchId} — pagina hoteis/voos materializados."""
        try:
            return self.api.call(
                "POST", f"/avail/package/search/{search_id}",
                params={"hotelPage": hotel_page, "flightPage": flight_page, "size": size},
                body={})
        except HttpError as exc:
            raise ClientFacingError(client_message_for_avail_error(exc.status, exc.body)) from None

    def orcamento(self, booking_rq: dict, *, confirmado: bool) -> dict:
        """POST /checkRate/budget — preco FIRME como ORCAMENTO (status QUOTATION).

        `confirmado=True` = o cliente aprovou a proposta no WhatsApp (botao/'sim').
        """
        if not confirmado:
            raise ClientFacingError(
                "Orcamento firme exige confirmacao explicita do cliente.")
        try:
            resp = self.api.call("POST", "/checkRate/budget", body=booking_rq)
        except HttpError as exc:
            raise ClientFacingError(client_message_for_avail_error(exc.status, exc.body)) from None
        return resp if isinstance(resp, dict) else {}


def extrair_precos(disponibilidade: dict, limite: int = 5) -> list:
    """Normaliza packageAvails em [{'pacote', 'hotel', 'preco', 'moeda', ...}].

    Defensivo quanto a nomes de campo: percorre candidatos conhecidos
    (lowestFare/total/amount/price/valor) em hotelAvails e no pacote.
    """
    saida = []
    for item in (disponibilidade.get("packageAvails") or [])[:limite]:
        pacote = item.get("package", {}) or {}
        hoteis = item.get("hotelAvails") or item.get("hoteis") or []
        if not hoteis:
            preco, moeda = _achar_preco(pacote) or (None, "BRL")
            if preco:
                saida.append({
                    "pacote": pacote.get("name") or pacote.get("nome"),
                    "pacote_id": pacote.get("id"), "hotel": None,
                    "preco": preco, "moeda": moeda or "BRL",
                    "inicio": (pacote.get("start") or "")[:10],
                    "fim": (pacote.get("end") or "")[:10],
                })
            continue
        for hotel in hoteis[:3]:
            preco, moeda = _achar_preco(hotel) or _achar_preco(pacote) or (None, "BRL")
            saida.append({
                "pacote": pacote.get("name") or pacote.get("nome"),
                "pacote_id": pacote.get("id"),
                "hotel": (hotel.get("hotel", {}) or {}).get("name") or hotel.get("name"),
                "preco": preco, "moeda": moeda or "BRL",
                "inicio": (pacote.get("start") or "")[:10],
                "fim": (pacote.get("end") or "")[:10],
            })
    return saida


def _achar_preco(obj: dict):
    candidatos = ("lowestFare", "total", "totalFare", "amount", "price",
                  "valor", "preco", "totalAmount")
    for chave in candidatos:
        valor = obj.get(chave)
        if isinstance(valor, (int, float)) and valor > 0:
            moeda = obj.get("currency") or obj.get("moeda") or "BRL"
            return float(valor), str(moeda)
        if isinstance(valor, dict):
            montante = valor.get("amount", valor.get("value", valor.get("total")))
            if isinstance(montante, (int, float)) and montante > 0:
                moeda = valor.get("currency") or obj.get("currency") or "BRL"
                return float(montante), str(moeda)
    return None
