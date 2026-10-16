# BOT_VIAGENS

WhatsApp travel-agent bot que extrai requisitos do cliente (slots), mantém estado
de conversa e retorna cotação/quote via **Infotravel API**.

- **Núcleo:** 100% Python padrão (stdlib) para os testes — sem dependências externas.
- **Serviço HTTP:** FastAPI + Uvicorn + Postgres (psycopg) e Redis (opcional/logs).
- **Gerenciador de estado:** máquina de estados offline (`novo → coletando → confirmando → cotando → proposta → humano/encerrado`), com dedupe por message ID, expiração de sessão e merge determinístico (nunca regride valor confirmado).
- **Infotravel:** GET `/avail/package/{tipo}` (disponibilidade), POST `/checkRate/budget` (orcamento firme sem pré-reserva).

---

## 1. Stack

| Serviço | Imagem | Porta | Papel |
|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5433→5432 | banco de sessões |
| `redis` | `redis:7-alpine` | — | cache (opcional no runtime) |
| `n8n` | `n8nio/n8n` | 5678 | orquestração WHP → bot |
| `evolution` | `atendai/evolution-api:v2` | 8080 | gateway WhatsApp |
| `bot` | build `./bot` | 8000 | API do bot |

---

## 2. Executando

```bash
# 1) Copiar .env.example → .env e preencher as credenciais
cp .env.example .env

# 2) Subir o stack
docker compose up --build -d

# 3) Verificar
curl http://localhost:8000/health
```

O bot expõe `http://localhost:8000` (n8n aponta `BOT_SERVICE_URL=http://bot:8000` no Docker).

---

## 3. Endpoints

### `GET /health`
Retorna o stage da sessão de "health" (fim de teste de conexão).

### `POST /v1/turn`
Turno completo do atendimento. O corpo é um JSON simples:

```json
{ "wa_id": "5511999999999", "text": "quero hotel em Gramado 12 a 17 de setembro" }
```

Responde:

```json
{
  "actions": [ { "type": "text", "text": "Resumo..." } ],
  "handoff": false,
  "state": { "stage": "confirmando", "faltando": [] }
}
```

Ao invocado pelo n8n (não pelo WhatsApp diretamente).

### Webhook do n8n (do lado da Evolution)

Evolution POSTa para `http://n8n:5678/webhook/whatsapp`. O payload é o padrão
Evolution Channel:

```json
{
  "numberId": "5511999999999",
  "key": { "remoteJid": "...", "fromMe": false, "id": "..." },
  "message": { "conversation": "olá" },
  "messageType": "text"
}
```

O workflow `n8n/workflows/whatsapp-to-bot.json` faz: parse → `/v1/turn` → envia
resposta via `{{EVOLUTION_API_URL}}/send-text/{{INSTANCE}}`.

---

## 4. Variáveis de ambiente

Copie o `.env.example` e preencha os campos destacados (`SEU_...`). Veja o
guia completo em `docs/CREDENCIAIS.md`.

```dotenv
POSTGRES_USER=bot
POSTGRES_PASSWORD=TROQUE_POR_SENHA_FORTE
POSTGRES_DB=botviagens
N8N_ENCRYPTION_KEY=TROQUE_POR_32_BYTES_HEX        # openssl rand -hex 32
EVOLUTION_API_KEY=TROQUE_POR_CHAVE_FORTE

INFOTRAVEL_ENV=homologacao
INFOTRAVEL_DOMAIN=SEU_DOMINIO_HOMOLOG.infotravel.com.br
INFOTRAVEL_USERNAME=seu-usuario
INFOTRAVEL_PASSWORD=sua-senha
INFOTRAVEL_CLIENT=SEU_CLIENT
INFOTRAVEL_AGENCY=2

LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=sk-...
```

---

## 5. Credenciais Infotravel

Guia e passos de como obter os valores de `docs/CREDENCIAIS.md` (acesso à
plataforma, cliente, agência e como redegar a senha segura).

---

## 6. Testes

```bash
cd bot
pip install -e ".[dev]"
python -m unittest discover -s tests -v
# ou:
pytest tests -q
```

Roda **todos os 39 testes** (núcleo offline + webapp HTTP). A API Infotravel é
chamada apenas nos testes `test_catalog_regiao` (que mockam o cliente) e
nunca no run padrão.

---

## 7. Fluxos do n8n

- `n8n/workflows/whatsapp-to-bot.json` — conversa completa (webhook → bot → reply).
- `n8n/workflows/smoke-test.json` — webhook `/webhook/smoke` que chama o bot e
  retorna o resultado como resposta HTTP (para teste rápido).

Após importar: definir **env vars** `BOT_SERVICE_URL=http://bot:8000`,
`EVOLUTION_API_URL=http://evolution:8080` e `INSTANCE=default` (no n8n, painel
 Environments → default).

---

## 8. Limpeza

```bash
docker compose down -v   # remove volumes (dados do postgres+redis)
```
