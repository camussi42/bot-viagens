"""Perguntas do bot: 1 por vez, com opcoes reais do catalogo quando possivel.

Ordem: tipo -> origem -> destino -> datas -> ocupacao.
(Origem vem antes do destino porque /searchEngine/.../destination exige origem.)
"""
from __future__ import annotations


def proxima_pergunta(estado: dict, opcoes: dict | None = None) -> dict:
    """Retorna {'campo', 'texto', 'botoes': [...]} ou {'campo': None} se completo."""
    opcoes = opcoes or {}
    if not estado["package_type"]["valor"]:
        return {"campo": "package_type",
                "texto": "O que você procura? Posso cotar hospedagem ou pacote completo.",
                "botoes": [{"id": "tipo:hotel", "label": "Só hospedagem"},
                           {"id": "tipo:hotel_flight", "label": "Hotel + aéreo"}]}
    if not estado["origem"]["texto"] and estado["package_type"]["valor"] != "hotel":
        lista = opcoes.get("origens", []) or []
        botoes = [{"id": f"orig:{o['id']}:{o.get('tipo', 'M')}",
                   "label": o["nome"].split(",")[0][:24]} for o in lista[:3]]
        return {"campo": "origem",
                "texto": "De onde você sai?",
                "botoes": botoes}
    if not estado["destino"]["texto"]:
        lista = opcoes.get("destinos", []) or []
        botoes = [{"id": f"dest:{o['id']}:{o.get('tipo', 'M')}",
                   "label": o["nome"].split(",")[0][:24]} for o in lista[:3]]
        return {"campo": "destino",
                "texto": "Para qual destino? (cidade ou região)",
                "botoes": botoes}
    if not estado["data_inicio"]["iso"] or not estado["data_fim"]["iso"]:
        periodos = opcoes.get("periodos", [])
        if periodos:
            sugestoes = []
            for p in periodos[:3]:
                fim = (p.get("ends") or [None])[0]
                sugestoes.append(f"{p['start']}" + (f" a {fim}" if fim else ""))
            return {"campo": "datas",
                    "texto": ("Quais as datas? Tenho saídas nestes períodos: "
                              + "; ".join(s for s in sugestoes if s)),
                    "botoes": []}
        return {"campo": "datas",
                "texto": "Quais as datas da viagem? (ex.: 12 a 17 de setembro)",
                "botoes": []}
    if not estado["adultos"]["valor"]:
        return {"campo": "adultos",
                "texto": "Quantas pessoas viajam? (ex.: 2 adultos e 1 criança de 9 anos)",
                "botoes": []}
    if estado["criancas_idades"]["valor"] in (None,):
        return {"campo": "criancas_idades",
                "texto": "Qual a idade das crianças? (o valor muda por idade)",
                "botoes": []}
    return {"campo": None, "texto": "", "botoes": []}
