"""Renderizacao de respostas em pt-BR prontas para o WhatsApp.

Deterministico: o LLM NAO formata preco. Numeros chegam prontos do quote.py.
"""
from __future__ import annotations


def brl(valor: float | int | None, moeda: str = "BRL") -> str:
    if valor is None:
        return "a consultar"
    texto = f"{float(valor):,.2f}"
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")
    simbolo = {"BRL": "R$", "USD": "US$", "EUR": "€"}.get((moeda or "BRL").upper(), moeda)
    return f"{simbolo} {texto}"


def data_br(iso: str | None) -> str:
    if not iso or len(iso) < 10:
        return "data a definir"
    ano, mes, dia = iso[:10].split("-")
    nomes = ["", "jan", "fev", "mar", "abr", "mai", "jun",
             "jul", "ago", "set", "out", "nov", "dez"]
    return f"{dia}/{mes}" if ano == "0000" else f"{dia} de {nomes[int(mes)]} de {ano}"


def resumo_confirmacao(slots: dict, tipo_rotulo: str = "Pacote") -> str:
    ocup = f"{slots.get('adultos', '?')} adulto(s)"
    if slots.get("criancas_idades"):
        ocup += f" + {len(slots['criancas_idades'])} criança(s)"
    return (f"Vou consultar: *{tipo_rotulo}* para *{slots.get('destino')}*, "
            f"saindo de *{slots.get('origem', 'a definir')}*, "
            f"de *{data_br(slots.get('data_inicio'))}* até *{data_br(slots.get('data_fim'))}*, "
            f"*{ocup}*. Confirma? ✅")


def mensagem_precos(precos: list, destino: str) -> str:
    if not precos:
        return (f"Não encontrei pacotes para *{destino}* nessas condições. "
                "Quer que eu busque outros períodos? 📅")
    linhas = [f"Encontrei estas opções para *{destino}* ✈️", ""]
    for i, p in enumerate(precos[:3], 1):
        hotel = f" — {p['hotel']}" if p.get("hotel") else ""
        linhas.append(f"{i}. *{p.get('pacote') or 'Pacote'}{hotel}*")
        linhas.append(f"   {data_br(p.get('inicio'))} → {data_br(p.get('fim'))} · "
                      f"a partir de *{brl(p.get('preco'), p.get('moeda'))}*")
        linhas.append("")
    linhas.append("Quer o valor fechado de alguma delas?")
    return "\n".join(linhas).strip()
