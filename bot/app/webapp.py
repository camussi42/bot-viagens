"""Serviço HTTP do bot: /health e /v1/turn (invocado pelo fluxo n8n)."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .db_store import MemoryStore
from .service import BotService

STORE = MemoryStore()
BOT = BotService(store=STORE)


app = FastAPI(title="Bot Viagens — cotação de pacotes")


class TurnRequest(BaseModel):
    wa_id: str
    text: str


class TurnResponse(BaseModel):
    actions: list[dict]
    handoff: bool
    state: dict


@app.get("/health")
def health():
    sessao = STORE.get_or_create_session("health", "health", "default")
    return {"ok": True, "stage": sessao.get("stage")}


@app.post("/v1/turn", response_model=TurnResponse)
def turn(payload: TurnRequest):
    """Um turno completo; o n8n já normalizou o texto antes de chamar."""
    if not payload.text.strip():
        raise HTTPException(status_code=400, detail="body.text obrigatorio")
    sessao = STORE.get_or_create_session(payload.wa_id, "web", "default")
    import time
    mid = f"http-{sessao['id']}-{int(time.time() * 1000)}"
    STORE.add_message(sessao["id"], "in", payload.text, mid)
    return BOT.turno({"wa_id": payload.wa_id, "name": "http"},
                     {"id": mid, "type": "text", "text": payload.text.strip()})
