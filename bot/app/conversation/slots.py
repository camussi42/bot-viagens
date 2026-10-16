"""Schema de slots da conversa (memoria de atendimento).

Cada slot guarda valor + confianca + origem (cliente|inferido|catalogo),
para o merge NUNCA regredir um dado ja confirmado pelo cliente.
"""
from __future__ import annotations

import re

TIPOS_PACOTE = ("hotel", "hotel_flight", "flight_service", "hotel_bus",
                "service_bus", "dynamic", "multidestination")

FLAGS_TIPO = {
    "hotel": ("so hotel", "só hotel", "somente hotel", "apenas hotel", "sem voo",
              "sem aéreo", "sem aereo", "hospedagem"),
    "hotel_flight": ("hotel + aéreo", "hotel+aereo", "hotel e voo", "com voo",
                     "com aéreo", "com aereo", "pacote com voo", "aéreo + hotel"),
}

OBRIGATORIOS = ("package_type", "destino", "data_inicio", "data_fim", "adultos")


def novo_estado() -> dict:
    return {
        "package_type": {"valor": None, "confianca": 0.0, "origem": None},
        "origem": {"texto": None, "id": None, "tipo": None, "confianca": 0.0, "origem": None},
        "destino": {"texto": None, "id": None, "tipo": None, "confianca": 0.0, "origem": None},
        "data_inicio": {"iso": None, "texto": None, "confianca": 0.0, "origem": None},
        "data_fim": {"iso": None, "texto": None, "confianca": 0.0, "origem": None},
        "adultos": {"valor": None, "confianca": 0.0, "origem": None},
        "criancas_idades": {"valor": [], "confianca": 0.0, "origem": None},
        "quartos": {"valor": 1, "confianca": 0.5, "origem": "padrao"},
        "nacionalidade": {"valor": "BR", "confianca": 0.5, "origem": "padrao"},
    }


def atualizar(estado: dict, extracao: dict) -> dict:
    """Merge: so escreve se confianca nova >= atual (nunca regride confirmado)."""
    estado = {k: dict(v) for k, v in estado.items()}
    for campo, novo in (extracao or {}).items():
        if campo not in estado or not isinstance(novo, dict):
            continue
        atual = estado[campo]
        if float(novo.get("confianca", 0)) >= float(atual.get("confianca", 0)):
            atual.update({k: v for k, v in novo.items() if v is not None})
            estado[campo] = atual
    return estado


def faltando(estado: dict) -> list:
    pend = []
    if not estado["package_type"]["valor"]:
        pend.append("package_type")
    if not estado["destino"]["texto"]:
        pend.append("destino")
    if not estado["data_inicio"]["iso"]:
        pend.append("data_inicio")
    if not estado["data_fim"]["iso"]:
        pend.append("data_fim")
    if not estado["adultos"]["valor"]:
        pend.append("adultos")
    if estado["criancas_idades"]["valor"] in (None,):
        pend.append("criancas_idades")
    return pend


def para_cotacao(estado: dict) -> dict:
    """Converte o estado nos parametros do avail/package."""
    return {
        "data_inicio": estado["data_inicio"]["iso"],
        "data_fim": estado["data_fim"]["iso"],
        "origem": {"id": estado["origem"]["id"], "tipo": estado["origem"]["tipo"]},
        "destino": {"id": estado["destino"]["id"], "tipo": estado["destino"]["tipo"]},
        "ocupacao": {"adultos": estado["adultos"]["valor"],
                     "criancas_idades": estado["criancas_idades"]["valor"] or [],
                     "quartos": estado["quartos"]["valor"] or 1},
        "nacionalidade": estado["nacionalidade"]["valor"] or "BR",
    }


def inferir_tipo(texto: str) -> tuple:
    """Heuristica rapida (o LLM confirma); retorna (tipo, confianca)."""
    t = (texto or "").lower()
    if any(f in t for f in FLAGS_TIPO["hotel_flight"]):
        return "hotel_flight", 0.75
    if "hotel" in t and not re.search(r"voo|a[eé]reo", t):
        return "hotel", 0.7
    if any(f in t for f in FLAGS_TIPO["hotel"]):
        return "hotel", 0.7
    return None, 0.0
