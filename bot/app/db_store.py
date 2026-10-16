"""Persistencia: protocolo + implementacao em memoria (testes/dev) + Postgres.

O Postgres e usado em runtime via driver `psycopg` (import lazy — o nucleo
e os testes rodam sem ele).
"""
from __future__ import annotations

import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol


class Store(Protocol):
    def get_or_create_session(self, wa_id: str, nome: str | None,
                              instance: str, ttl_hours: int = 24) -> dict: ...
    def save_session(self, sessao: dict) -> None: ...
    def seen_message(self, sessao_id: str, wa_message_id: str) -> bool: ...
    def add_message(self, sessao_id: str, direcao: str, texto: str,
                    wa_message_id: str | None = None, intencao: str = "") -> None: ...
    def history(self, sessao_id: str, limite: int = 20) -> list: ...


def _agora():
    return datetime.now(timezone.utc)


class MemoryStore:
    """Store em memoria, thread-safe. Ideal p/ testes e smoke test local."""

    def __init__(self):
        self._lock = threading.Lock()
        self._sessoes: dict = {}
        self._vistas: set = set()
        self._mensagens: dict = {}

    def get_or_create_session(self, wa_id, nome, instance, ttl_hours=24):
        with self._lock:
            for sessao in self._sessoes.values():
                if (sessao["wa_id"] == wa_id and not sessao.get("handoff")
                        and sessao.get("expira_em") and sessao["expira_em"] > _agora()):
                    return dict(sessao)
            sid = str(uuid.uuid4())
            sessao = {"id": sid, "wa_id": wa_id, "nome": nome, "instance": instance,
                      "stage": "novo", "estado": None, "tentativas": 0, "handoff": False,
                      "expira_em": _agora() + timedelta(hours=ttl_hours)}
            self._sessoes[sid] = sessao
            self._mensagens[sid] = []
            return dict(sessao)

    def save_session(self, sessao):
        with self._lock:
            atual = self._sessoes.get(sessao["id"], {})
            atual.update({k: v for k, v in sessao.items() if k != "id"})
            atual["expira_em"] = _agora() + timedelta(hours=24)
            self._sessoes[sessao["id"]] = atual

    def seen_message(self, sessao_id, wa_message_id):
        if not wa_message_id:
            return False
        with self._lock:
            chave = (sessao_id, wa_message_id)
            if chave in self._vistas:
                return True
            self._vistas.add(chave)
            return False

    def add_message(self, sessao_id, direcao, texto, wa_message_id=None, intencao=""):
        with self._lock:
            self._mensagens.setdefault(sessao_id, []).append(
                {"direcao": direcao, "texto": texto,
                 "wa_message_id": wa_message_id, "intencao": intencao})

    def history(self, sessao_id, limite=20):
        with self._lock:
            return list(self._mensagens.get(sessao_id, [])[-limite:])


import json


class PgStore:
    """Adaptador Postgres (tabelas em bot/sql/001_schema.sql)."""

    def __init__(self, dsn: str):
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("psycopg nao instalado (pip install '.[runtime]')") from exc
        self._psycopg = psycopg
        self._dsn = dsn

    def _cx(self):
        return self._psycopg.connect(self._dsn, autocommit=True)

    def get_or_create_session(self, wa_id, nome, instance, ttl_hours=24):
        with self._cx() as cx:
            row = cx.execute(
                """SELECT s.id, s.stage, s.slots, s.tentativas, s.handoff
                     FROM sessoes s JOIN contatos c ON c.id = s.contato_id
                    WHERE c.wa_id = %s AND s.expira_em > now() AND NOT s.handoff
                    ORDER BY s.ultima_msg_em DESC NULLS LAST LIMIT 1""",
                (wa_id,)).fetchone()
            if row:
                return {"id": str(row[0]), "wa_id": wa_id, "nome": nome,
                        "instance": instance, "stage": row[1],
                        "estado": row[2], "tentativas": row[3] or 0,
                        "handoff": bool(row[4]), "expira_em": None}
            cx.execute("INSERT INTO contatos (wa_id, nome) VALUES (%s, %s) "
                       "ON CONFLICT (wa_id) DO UPDATE SET nome = COALESCE(EXCLUDED.nome, contatos.nome)",
                       (wa_id, nome))
            contato = cx.execute("SELECT id FROM contatos WHERE wa_id = %s",
                                 (wa_id,)).fetchone()
            sid = cx.execute(
                """INSERT INTO sessoes (contato_id, instance, stage, slots, expira_em)
                   VALUES (%s, %s, 'novo', '{}', now() + (%s || ' hours')::interval)
                   RETURNING id""", (contato[0], instance, str(ttl_hours))).fetchone()
            return {"id": str(sid[0]), "wa_id": wa_id, "nome": nome,
                    "instance": instance, "stage": "novo", "estado": None,
                    "tentativas": 0, "handoff": False, "expira_em": None}

    def save_session(self, sessao):
        with self._cx() as cx:
            cx.execute(
                """UPDATE sessoes SET stage=%s, slots=%s::jsonb, tentativas=%s,
                          handoff=%s, ultima_msg_em=now(), expira_em=now() + interval '24 hours'
                   WHERE id=%s""",
                (sessao.get("stage"), json.dumps(sessao.get("estado") or {}, ensure_ascii=False),
                 sessao.get("tentativas", 0), bool(sessao.get("handoff")), sessao["id"]))

    def seen_message(self, sessao_id, wa_message_id):
        if not wa_message_id:
            return False
        with self._cx() as cx:
            try:
                cx.execute("INSERT INTO mensagens (sessao_id, direcao, wa_message_id, texto) "
                           "VALUES (%s, 'in', %s, '')", (sessao_id, wa_message_id))
                return False
            except Exception:
                return True

    def add_message(self, sessao_id, direcao, texto, wa_message_id=None, intencao=""):
        with self._cx() as cx:
            cx.execute("INSERT INTO mensagens (sessao_id, direcao, texto, wa_message_id, intencao) "
                       "VALUES (%s, %s, %s, %s, %s)",
                       (sessao_id, direcao, texto, wa_message_id, intencao))

    def history(self, sessao_id, limite=20):
        with self._cx() as cx:
            rows = cx.execute(
                "SELECT direcao, texto FROM mensagens WHERE sessao_id=%s "
                "ORDER BY id DESC LIMIT %s", (sessao_id, limite)).fetchall()
            return [{"direcao": r[0], "texto": r[1]} for r in reversed(rows)]
