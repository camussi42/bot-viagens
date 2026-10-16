"""Parse defensivo de datas em portugues (sem dependencias).

Cobre: "12/09", "12/09/2026", "12 de setembro", "dia 12", "amanhã",
"semana que vem", "próximo mês", "feriado". Para feriados moveis/fixos
usa tabela em feriados.py (a criar). Retorna ISO YYYY-MM-DD ou None.
"""
from __future__ import annotations

import re
from datetime import date, timedelta

MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}

_RX_NUM = re.compile(r"\b(\d{1,2})[/\-.](\d{1,2})(?:[/\-.](\d{2,4}))?\b")
_RX_EXT = re.compile(r"\b(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?", re.I)
_RX_DIA = re.compile(r"\bdia\s+(\d{1,2})\b", re.I)


def _completar_ano(dia: int, mes: int, hoje: date, ano: int | None = None) -> date | None:
    try:
        if ano:
            return date(ano if ano >= 100 else 2000 + ano, mes, dia)
        cand = date(hoje.year, mes, dia)
        if cand < hoje - timedelta(days=1):  # tolerancia: ontem/hoje = este ano
            cand = date(hoje.year + 1, mes, dia)
        return cand
    except ValueError:
        return None


def parse_data(texto: str, hoje: date | None = None) -> str | None:
    hoje = hoje or date.today()
    t = (texto or "").strip().lower()
    if not t:
        return None
    if "amanh" in t:
        return (hoje + timedelta(days=1)).isoformat()
    if "depois de amanh" in t:
        return (hoje + timedelta(days=2)).isoformat()
    if "hoje" in t:
        return hoje.isoformat()
    if "semana que vem" in t or "proxima semana" in t or "próxima semana" in t:
        return (hoje + timedelta(days=7 - hoje.weekday())).isoformat()
    if "proximo mes" in t or "próximo mes" in t or "próximo mês" in t or "mes que vem" in t or "mês que vem" in t:
        mes = hoje.month + 1 if hoje.month < 12 else 1
        ano = hoje.year if hoje.month < 12 else hoje.year + 1
        return date(ano, mes, 1).isoformat()
    m = _RX_NUM.search(t)
    if m:
        dia, mes = int(m.group(1)), int(m.group(2))
        ano = int(m.group(3)) if m.group(3) else None
        if 1 <= mes <= 12:
            dt = _completar_ano(dia, mes, hoje, ano)
            return dt.isoformat() if dt else None
    m = _RX_EXT.search(t)
    if m:
        mes = MESES.get(m.group(2).lower())
        if mes:
            dt = _completar_ano(int(m.group(1)), mes, hoje,
                                int(m.group(3)) if m.group(3) else None)
            return dt.isoformat() if dt else None
    m = _RX_DIA.search(t)
    if m:
        dia = int(m.group(1))
        for delta_mes in (0, 1):
            mes = hoje.month + delta_mes
            ano = hoje.year + (1 if mes > 12 else 0)
            mes = mes if mes <= 12 else mes - 12
            try:
                cand = date(ano, mes, dia)
            except ValueError:
                continue
            if cand >= hoje - timedelta(days=1):
                return cand.isoformat()
    return None


def parse_idades_criancas(texto: str) -> list:
    """Extrai idades de crianca: 'criança de 9', 'filhos de 4 e 7 anos', '2 crianças (9 e 4)'."""
    t = (texto or "").lower()
    padroes = [
        r"crian[çc]as?\s+(?:de\s+|com\s+)?(\d{1,2})(?:\s*e\s*(\d{1,2}))?(?:\s*e\s*(\d{1,2}))?",
        r"filh[oa]s?\s+(?:de\s+)?(\d{1,2})(?:\s*e\s*(\d{1,2}))?(?:\s*e\s*(\d{1,2}))?",
        r"\((\d{1,2})\s*e\s*(\d{1,2})\)",
        r"de\s+(\d{1,2})\s*e\s+(\d{1,2})\s*anos",
    ]
    for padrao in padroes:
        m = re.search(padrao, t)
        if m:
            idades = [int(g) for g in m.groups() if g and g.isdigit()]
            if idades and all(0 <= i <= 17 for i in idades):
                return idades
    return []


def parse_adultos(texto: str) -> int | None:
    t = (texto or "").lower()
    m = re.search(r"(\d+)\s+adultos?", t)
    if m:
        return int(m.group(1))
    if re.search(r"\bsozinho\b|\b1 pessoa\b|\bpra 1\b|\bpara 1\b", t):
        return 1
    m = re.search(r"\b(um|uma|dois|duas|tres|três|quatro)\b\s+adulto", t)
    if m:
        mapa = {"um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "três": 3, "quatro": 4}
        return mapa[m.group(1)]
    return None
