"""Traducao de erros da API Infotravel para linguagem de cliente.

Fatos vindos dos guias oficiais (MCP get_flow_guide):
- `destination`/`destinationType` sao OBRIGATORIOS em GET /avail/package/{tipo}.
  Sem eles: HTTP 400 com exceptionCode 1278 e mensagem "Destino nao encontrado",
  que NAO significa "sem oferta".
- `destination` quer id de REGIAO (ex.: Sao Paulo = 2802). Id de MUNICIPIO
  (ex.: utility/county/Sao Paulo -> 23500) e outro espaco de ids — 23500 como
  regiao e Alfreton, na Inglaterra.
- `origin` aceita regiao ou aeroporto, desde que originType combine:
  origin=2732&originType=M  ==  origin=8249&originType=A (GIG).
  Cruzar espacos (2732&A, ou originIata=GIG sozinho) responde "No availability".
- Status de reserva: 21 valores; desconhecido => "consultar depois", nunca erro.
"""
from __future__ import annotations


class ClientFacingError(Exception):
    """Erro seguro de mostrar ao cliente no WhatsApp."""


DESTINO_NAO_ENCONTRADO = {1278}

MENSAGENS = {
    1278: ("Hmm, nao encontrei esse destino no catalogo de pacotes com esse nome. "
            "Me diga de outro jeito (ex.: cidade + estado) ou escolha uma opcao que vou te mostrar."),
    "no_availability": ("Nao encontrei saida para essas datas/destino. "
                        "Quer que eu mostre os periodos com saida disponivel?"),
    "timeout": ("A consulta demorou mais que o esperado (os fornecedores estao lentos). "
                "Posso tentar de novo agora?"),
    "indisponivel": ("O sistema de cotacao esta indisponivel no momento. "
                     "Ja avisei um atendente, que te responde em instantes."),
    "auth": ("Estamos com instabilidade na conexao com o sistema de reservas. "
             "Um atendente ja foi avisado."),
}


def client_message_for_avail_error(status: int, body) -> str:
    """Mapeia erro do avail/package para texto amigavel. Nunca vaza detalhe tecnico."""
    code = None
    if isinstance(body, dict):
        for chave in ("exceptionCode", "code", "errorCode"):
            if chave in body:
                code = body[chave]
                break
        mensagem = str(body.get("message", body.get("mensagem", "")) or "")
    else:
        mensagem = str(body or "")
    if code in DESTINO_NAO_ENCONTRADO or "Destino n" in mensagem:
        return MENSAGENS[1278]
    if status == 400 or "No availability" in mensagem:
        return MENSAGENS["no_availability"]
    if status in (502, 503, 504):
        return MENSAGENS["timeout"]
    if status in (500,) or status >= 500:
        return MENSAGENS["indisponivel"]
    return MENSAGENS["indisponivel"]


# Subconjunto util dos 21 status de reserva: o que o BOT pode encontrar
# ao consultar cotacoes (QUOTATION) ou pre-reservas (CREATION).
STATUS_EM_MOVIMENTO = {"CREATION", "QUOTATION", "PROCESSING", "IN_PAYMENT_PROCESS",
                       "EMISSION", "EDITION", "IN_CANCELLATION_PROCESS"}
STATUS_AGUARDANDO = {"ORDER", "ON_REQUEST", "WAITING_LIST", "ANALYSIS"}
STATUS_VALIDOS = {"RESERVED", "CONFIRMED", "MODIFIED"}
STATUS_ENCERRADOS = {"CANCELED", "EXPIRED", "DENIED", "INCONSISTENT",
                     "BLOCKED", "NOT_INTEGRATED", "EMPTY"}


def status_para_cliente(status: str) -> str:
    s = (status or "").upper()
    if s in STATUS_EM_MOVIMENTO:
        return "em processamento"
    if s in STATUS_AGUARDANDO:
        return "aguardando confirmacao do fornecedor"
    if s in STATUS_VALIDOS:
        return "confirmada"
    if s in STATUS_ENCERRADOS:
        return "encerrada"
    return "em verificacao"  # caso padrao: status novo nunca derruba a integracao
