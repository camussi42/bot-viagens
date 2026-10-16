"""Extracao de slots a partir de texto livre (pt-BR) e de cliques em botao.

Funciona 100% offline (heuristicas + regex). O LLM entra depois implementando
a mesma interface `extrair(texto, hoje) -> dict`, com confiancas maiores.
Botoes do WhatsApp injetam slots com confianca 1.0 (origem 'cliente').
"""
from __future__ import annotations

import re
from datetime import date

from . import dates, slots

_PALAVRAS_TEMPO = {"hoje", "amanha", "amanhã", "semana", "mes", "mês",
                   "feriado", "feriadao", "feriadão", "final",
                   "janeiro", "fevereiro", "marco", "março", "abril", "maio",
                   "junho", "julho", "agosto", "setembro", "outubro",
                   "novembro", "dezembro", "segunda", "terca", "terça",
                   "quarta", "quinta", "sexta", "sabado", "sábado", "domingo"}

_RX_DESTINO = re.compile(
    r"(?:\bpara\b|\bpra\b|\bpro\b|\bem\b|\bno\b|\bna\b)\s+"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{1,40}?)"
    r"(?=\s+(?:em|de|do|da|dos|das|com|para|pra|pro|nos|nas|no|na|e|a|dia)\b"
    r"|\s*\d|[,.!?]|$)",
    re.I)
_RX_ORIGEM = re.compile(
    r"(?:saindo de|sair de|sai de|desde|origem:?)\s+"
    r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ .'-]{1,40}?)"
    r"(?=\s+(?:para|pra|pro|em|com|e|de|dia)\b|\s*\d|[,.!?]|$)",
    re.I)

_RX_PERIODO_MES = re.compile(
    r"(\d{1,2})\s*(?:a|à|ate|até|-)\s*(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?", re.I)
_RX_PERIODO_DUPLO = re.compile(
    r"(\d{1,2})\s+de\s+([a-zç]+)\s*(?:a|à|ate|até)\s*(\d{1,2})\s+de\s+([a-zç]+)", re.I)
_RX_PERIODO_NUM = re.compile(
    r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\s*(?:a|à|ate|até|-)\s*"
    r"(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?")


def _cidade_valida(captura: str | None) -> str | None:
    if not captura:
        return None
    nome = re.sub(r"\s+", " ", captura).strip().strip(".,!?")
    palavras = nome.split()
    if not (1 <= len(palavras) <= 3) or any(p.isdigit() for p in palavras):
        return None
    if any(p.lower() in _PALAVRAS_TEMPO for p in palavras):
        return None
    if len(nome) < 3:
        return None
    return nome


def parse_cidades(texto: str) -> tuple:
    """Retorna (origem_texto, destino_texto). Heuristica conservadora."""
    t = texto or ""
    origem = destino = None
    m = _RX_ORIGEM.search(t)
    if m:
        origem = _cidade_valida(m.group(1))
    m = _RX_DESTINO.search(t)
    if m:
        destino = _cidade_valida(m.group(1))
    return origem, destino


def parse_periodo(texto: str, hoje: date | None = None) -> tuple:
    """Retorna (iso_inicio, iso_fim|None): '12 a 17 de setembro',
    '28 de junho a 3 de julho', '12/09 a 17/09'."""
    hoje = hoje or date.today()
    t = texto or ""
    m = _RX_PERIODO_MES.search(t)
    if m:
        mes = dates.MESES.get(m.group(3).lower())
        if mes:
            ano = int(m.group(4)) if m.group(4) else None
            ini = dates._completar_ano(int(m.group(1)), mes, hoje, ano)
            fim_ano = ano or (ini.year if ini else None)
            fim = dates._completar_ano(int(m.group(2)), mes, hoje, fim_ano)
            if ini and fim and fim >= ini:
                return ini.isoformat(), fim.isoformat()
    m = _RX_PERIODO_DUPLO.search(t)
    if m:
        mes1 = dates.MESES.get(m.group(2).lower())
        mes2 = dates.MESES.get(m.group(4).lower())
        if mes1 and mes2:
            ini = dates._completar_ano(int(m.group(1)), mes1, hoje)
            ano_fim = (ini.year + 1) if ini and mes2 < mes1 else (ini.year if ini else None)
            fim = dates._completar_ano(int(m.group(3)), mes2, hoje, ano_fim)
            if ini and fim and fim >= ini:
                return ini.isoformat(), fim.isoformat()
    m = _RX_PERIODO_NUM.search(t)
    if m:
        ano1 = int(m.group(3)) if m.group(3) else None
        ano2 = int(m.group(6)) if m.group(6) else ano1
        ini = dates._completar_ano(int(m.group(1)), int(m.group(2)), hoje, ano1)
        fim = dates._completar_ano(int(m.group(4)), int(m.group(5)), hoje, ano2)
        if ini and fim and fim >= ini:
            return ini.isoformat(), fim.isoformat()
    return dates.parse_data(t, hoje), None


def heuristic_extract(texto: str, hoje: date | None = None) -> dict:
    """Extracao offline. Confiancas moderadas (o LLM usa maiores)."""
    hoje = hoje or date.today()
    t = texto or ""
    out: dict = {}
    tipo, conf = slots.inferir_tipo(t)
    if tipo:
        out["package_type"] = {"valor": tipo, "confianca": conf, "origem": "heuristica"}
    origem_txt, destino_txt = parse_cidades(t)
    if origem_txt:
        out["origem"] = {"texto": origem_txt, "confianca": 0.6, "origem": "heuristica"}
    if destino_txt:
        out["destino"] = {"texto": destino_txt, "confianca": 0.6, "origem": "heuristica"}
    inicio, fim = parse_periodo(t, hoje)
    if inicio:
        out["data_inicio"] = {"iso": inicio, "texto": t[:80], "confianca": 0.7,
                              "origem": "heuristica"}
    if fim:
        out["data_fim"] = {"iso": fim, "texto": t[:80], "confianca": 0.7,
                           "origem": "heuristica"}
    adultos = dates.parse_adultos(t)
    if adultos:
        out["adultos"] = {"valor": adultos, "confianca": 0.85, "origem": "heuristica"}
    idades = dates.parse_idades_criancas(t)
    if idades:
        out["criancas_idades"] = {"valor": idades, "confianca": 0.85, "origem": "heuristica"}
    elif re.search(r"crian[çc]a|filh[oa]|menor", t.lower()) and not adultos:
        # Mencao a crianca sem idade: forca a pergunta da idade.
        out["criancas_idades"] = {"valor": None, "confianca": 0.4, "origem": "heuristica"}
    return out


def button_extract(button_id: str) -> dict:
    """Cliques em botao do proprio bot: confianca total.

    Formatos: 'tipo:hotel_flight' | 'orig:2732:M' | 'dest:15767:M' |
              'period:2026-09-12:2026-09-17'  ('conf:*' vira texto, tratado fora)
    """
    if not button_id or ":" not in button_id:
        return {}
    kind, _, resto = button_id.partition(":")
    if kind == "tipo" and resto in slots.TIPOS_PACOTE:
        return {"package_type": {"valor": resto, "confianca": 1.0, "origem": "cliente"}}
    partes = resto.split(":")
    if kind == "orig" and len(partes) >= 1 and partes[0].isdigit():
        tipo = (partes[1] if len(partes) > 1 else "M").upper()
        return {"origem": {"id": int(partes[0]), "tipo": tipo,
                           "confianca": 1.0, "origem": "cliente"}}
    if kind == "dest" and len(partes) >= 1 and partes[0].isdigit():
        tipo = (partes[1] if len(partes) > 1 else "M").upper()
        return {"destino": {"id": int(partes[0]), "tipo": tipo,
                            "confianca": 1.0, "origem": "cliente"}}
    if kind == "period" and len(partes) >= 2:
        return {"data_inicio": {"iso": partes[0], "texto": "botao",
                                "confianca": 1.0, "origem": "cliente"},
                "data_fim": {"iso": partes[1], "texto": "botao",
                             "confianca": 1.0, "origem": "cliente"}}
    return {}

