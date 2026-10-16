"""Orquestrador de um turno de conversa (nucleo, sem dependencias externas).

Pipeline: normalizar entrada -> extrair (heuristica; LLM depois) -> maquina
de estados -> (quando completo) cotacao Infotravel -> acoes de resposta.
Funciona OFFLINE: sem credenciais/mocks, atende ate o stage de confirmacao.
"""
from __future__ import annotations

from datetime import date

from .conversation import extract, machine as sm, render, slots
from .db_store import MemoryStore
from .infotravel import auth as auth_mod
from .infotravel.catalog import CatalogClient
from .infotravel.errors import ClientFacingError
from .infotravel.quote import QuoteClient, extrair_precos
from .infotravel.settings import from_env as settings_from_env

ROTULOS_TIPO = {"hotel": "Hospedagem", "hotel_flight": "Hotel + aéreo",
                "hotel_bus": "Hotel + ônibus", "dynamic": "Pacote dinâmico"}


class NaoConfigurado(Exception):
    pass


class BotService:
    def __init__(self, store=None, settings=None, api_client=None,
                 catalog=None, quote=None, hoje=None, llm=None):
        self.store = store or MemoryStore()
        self.settings = settings
        self._api_client = api_client
        self._catalog = catalog
        self._quote = quote
        self._hoje = hoje or (lambda: date.today())
        self.llm = llm  # interface futura: llm.extrair(texto) -> dict

    # -- infra lazy -----------------------------------------------------
    def _settings(self):
        if self.settings is None:
            import os
            self.settings = settings_from_env(os.environ.get)
        return self.settings

    def _api(self):
        if self._api_client is None:
            cfg = self._settings()
            if not cfg.configured:
                raise NaoConfigurado("Infotravel sem credenciais: " + ", ".join(cfg.missing()))
            self._api_client = auth_mod.ApiClient(cfg)
        return self._api_client

    def _catalogo(self):
        if self._catalog is None:
            self._catalog = CatalogClient(self._api())
        return self._catalog

    def _cotador(self):
        if self._quote is None:
            self._quote = QuoteClient(self._api())
        return self._quote

    # -- turno -----------------------------------------------------------
    def turno(self, contato: dict, mensagem: dict, instance: str = "default") -> dict:
        wa_id = contato.get("wa_id", "")
        sessao = self.store.get_or_create_session(wa_id, contato.get("name"), instance)
        mid = mensagem.get("id")
        if mid and self.store.seen_message(sessao["id"], mid):
            return {"actions": [], "duplicada": True, "state": {"stage": sessao.get("stage")}}
        texto = (mensagem.get("text") or "").strip()
        self.store.add_message(sessao["id"], "in", texto, mid)

        if mensagem.get("type") == "button" and mensagem.get("button_id"):
            bid = mensagem["button_id"]
            if bid.startswith("conf:"):
                texto = "sim" if bid == "conf:sim" else "não"
                extracao = {}
            else:
                extracao = extract.button_extract(bid)
        else:
            extracao = self._extrair(texto)

        opcoes = self._opcoes(sessao, extracao)
        resultado = sm.passo(sessao, texto, extracao, opcoes)
        actions = self._acoes(sessao, resultado)
        if not sessao.get("estado") or not isinstance(sessao["estado"], dict):
            sessao["estado"] = slots.novo_estado()
        self.store.save_session(sessao)
        for acao in actions:
            if acao.get("type") in ("text", "buttons"):
                self.store.add_message(sessao["id"], "out", acao.get("text", ""))
        estado = sessao.get("estado") or {}
        return {"actions": actions, "handoff": resultado.get("handoff", False),
                "state": {"stage": sessao.get("stage"),
                          "faltando": slots.faltando(estado)}}

    def _extrair(self, texto: str) -> dict:
        base = extract.heuristic_extract(texto, self._hoje())
        if self.llm is None:
            return base
        try:
            refinada = self.llm.extrair(texto) or {}
        except Exception:
            return base
        for campo, valor in base.items():
            refinada.setdefault(campo, valor)
        return refinada

    # -- catalogo p/ perguntas -------------------------------------------
    def _opcoes(self, sessao: dict, extracao: dict) -> dict:
        try:
            tipo = (extracao.get("package_type") or {}).get("valor") \
                or ((sessao.get("estado") or {}).get("package_type") or {}).get("valor")
            if not tipo:
                return {}
            cat = self._catalogo()
            origens = [{"id": o.id, "nome": o.nome, "tipo": o.tipo or "M"}
                       for o in cat.origens(tipo)[:10]]
            estado_ant = sessao.get("estado") or {}
            origem_txt = (extracao.get("origem") or {}).get("texto") \
                or (estado_ant.get("origem") or {}).get("texto")
            origem_id = (extracao.get("origem") or {}).get("id") \
                or (estado_ant.get("origem") or {}).get("id")
            origem = None
            if origem_id:
                origem = next((o for o in origens if o["id"] == origem_id), None)
            elif origem_txt:
                achada = CatalogClient.achar_por_nome(
                    [type("O", (), o)() for o in origens], origem_txt)
                if achada:
                    origem = {"id": achada.id, "nome": achada.nome, "tipo": achada.tipo}
            saida = {"origens": origens}
            if origem:
                saida["destinos"] = [
                    {"id": d.id, "nome": d.nome, "tipo": d.tipo or "M"}
                    for d in cat.destinos(tipo, origem["id"], origem.get("tipo") or "M")[:10]]
            return saida
        except (NaoConfigurado, Exception):
            return {}  # offline: perguntas sem opcoes do catalogo

    # -- acoes de resposta -------------------------------------------------
    def _acoes(self, sessao: dict, resultado: dict) -> list:
        pergunta = resultado.get("pergunta")
        if resultado["stage"] == sm.STAGE_COTANDO:
            return self._cotar(sessao)
        if pergunta is None:
            return []
        texto = pergunta.get("texto") or ""
        if pergunta.get("campo") == "confirmacao":
            cfg = self._resumo_slots(sessao)
            texto = render.resumo_confirmacao(
                cfg, ROTULOS_TIPO.get(cfg.get("tipo"), "Pacote"))
        acao = {"type": "text", "text": texto}
        botoes = pergunta.get("botoes") or []
        if botoes:
            return [acao, {"type": "buttons", "text": "Toque em uma opção 👇",
                           "buttons": botoes[:3]}]
        return [acao]

    def _resumo_slots(self, sessao: dict) -> dict:
        estado = sessao.get("estado") or {}
        origem = estado.get("origem") or {}
        destino = estado.get("destino") or {}
        return {
            "tipo": (estado.get("package_type") or {}).get("valor"),
            "origem": origem.get("texto") or f"id {origem.get('id')}",
            "destino": destino.get("texto") or f"id {destino.get('id')}",
            "data_inicio": (estado.get("data_inicio") or {}).get("iso"),
            "data_fim": (estado.get("data_fim") or {}).get("iso"),
            "adultos": (estado.get("adultos") or {}).get("valor"),
            "criancas_idades": (estado.get("criancas_idades") or {}).get("valor") or [],
        }

    def _cotar(self, sessao: dict) -> list:
        try:
            cfg = slots.para_cotacao(sessao.get("estado") or {})
            tipo = (sessao.get("estado") or {}).get("package_type", {}).get("valor")
            disp = self._cotador().disponibilidade(tipo, cfg)
        except NaoConfigurado:
            sessao["stage"] = sm.STAGE_CONFIRMANDO
            cfg = self._resumo_slots(sessao)
            return [{"type": "text", "text":
                     "Cotação real ainda não configurada (faltam as credenciais "
                     "da API Infotravel). Seu resumo está salvo: "
                     + render.resumo_confirmacao(
                         cfg, ROTULOS_TIPO.get(cfg.get("tipo"), "Pacote"))}]
        except ClientFacingError as exc:
            sessao["stage"] = sm.STAGE_COLETANDO
            return [{"type": "text", "text": str(exc)}]
        precos = extrair_precos(disp)
        destino = ((sessao.get("estado") or {}).get("destino") or {}).get("texto") or "seu destino"
        sessao["stage"] = sm.STAGE_PROPOSTA
        return [{"type": "text", "text": render.mensagem_precos(precos, destino)}]
