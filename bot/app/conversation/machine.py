"""Maquina de estados do atendimento (sem dependencias externas)."""
from __future__ import annotations

from . import questions, slots

STAGE_NOVO = "novo"
STAGE_COLETANDO = "coletando"
STAGE_CONFIRMANDO = "confirmando"
STAGE_COTANDO = "cotando"
STAGE_PROPOSTA = "proposta"
STAGE_HUMANO = "humano"
STAGE_ENCERRADO = "encerrado"

MAX_TENTATIVAS = 3
PEDIDOS_HUMANO = ("atendente", "humano", "pessoa", "alguém", "alguem",
                  "ligar", "telefone", "whatsapp da agência", "whatsapp da agencia")

INTENCOES_HUMANO = ("reclama", "insatisfe", "péssimo", "pessimo", "horrível",
                    "horrivel", "absurdo", "cancelar")


def quer_humano(texto: str) -> bool:
    t = (texto or "").lower()
    return any(p in t for p in PEDIDOS_HUMANO) or any(i in t for i in INTENCOES_HUMANO)


def sim_ou_nao(texto: str) -> str | None:
    t = (texto or "").strip().lower()
    if t in ("sim", "s", "yes", "confirmo", "confirmado", "pode ser", "ok",
             "isso", "isso mesmo", "perfeito", "fechado", "bora", "vamos", "✅", "👍"):
        return "sim"
    if t in ("não", "nao", "n", "no", "cancelar", "errado", "não é isso", "nao e isso"):
        return "nao"
    return None


def passo(sessao: dict, texto: str, extracao: dict, opcoes: dict | None = None) -> dict:
    """Um turno da conversa. Retorna {'stage', 'estado', 'pergunta'|'acoes', 'handoff'}."""
    opcoes = opcoes or {}
    estado = sessao.get("estado") or slots.novo_estado()
    if sessao.get("stage") in (None, STAGE_NOVO):
        sessao["stage"] = STAGE_COLETANDO
    if sessao.get("stage") == STAGE_HUMANO:
        return {"stage": STAGE_HUMANO, "estado": estado, "handoff": True, "pergunta": None}

    if quer_humano(texto):
        sessao["stage"] = STAGE_HUMANO
        return {"stage": STAGE_HUMANO, "estado": estado, "handoff": True,
                "pergunta": {"campo": None,
                             "texto": ("Claro! Vou te passar para um atendente agora. "
                                       "Só um instante 🙏"),
                             "botoes": []}}

    if sessao.get("stage") == STAGE_CONFIRMANDO:
        resposta = sim_ou_nao(texto)
        if resposta == "nao":
            sessao["stage"] = STAGE_COLETANDO
            sessao["tentativas"] = sessao.get("tentativas", 0) + 1
            return {"stage": STAGE_COLETANDO, "estado": estado, "handoff": False,
                    "pergunta": {"campo": "correcao",
                                 "texto": "Sem problema! O que devo corrigir? "
                                          "(destino, datas, pessoas...)",
                                 "botoes": []}}
        if resposta == "sim":
            sessao["stage"] = STAGE_COTANDO
            return {"stage": STAGE_COTANDO, "estado": estado, "handoff": False,
                    "pergunta": None}

    estado = slots.atualizar(estado, extracao)
    sessao["estado"] = estado
    pendentes = slots.faltando(estado)

    if not pendentes:
        sessao["stage"] = STAGE_CONFIRMANDO
        sessao["tentativas"] = 0
        return {"stage": STAGE_CONFIRMANDO, "estado": estado, "handoff": False,
                "pergunta": {"campo": "confirmacao", "texto": "__RESUMO__", "botoes": [
                    {"id": "conf:sim", "label": "✅ Confirmar"},
                    {"id": "conf:nao", "label": "✏️ Corrigir"}]}}

    sessao["tentativas"] = sessao.get("tentativas", 0) + 1
    if sessao["tentativas"] >= MAX_TENTATIVAS:
        sessao["stage"] = STAGE_HUMANO
        return {"stage": STAGE_HUMANO, "estado": estado, "handoff": True,
                "pergunta": {"campo": None,
                             "texto": ("Não estou conseguindo entender — vou te passar "
                                       "para um atendente que resolve rapidinho 🙏"),
                             "botoes": []}}
    sessao["stage"] = STAGE_COLETANDO
    return {"stage": STAGE_COLETANDO, "estado": estado, "handoff": False,
            "pergunta": questions.proxima_pergunta(estado, opcoes)}
