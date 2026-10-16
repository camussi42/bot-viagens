# Fluxo n8n — documentação de integração

Este diretório documenta como o **n8n** fala com o serviço do bot (`app/webapp.py`)
e devolve a resposta pelo canal WhatsApp (Evolution API). O código já está no
repositório em `n8n/workflows/`.

---

## Fluxo `whatsapp-to-bot`

```
WhatsApp (Evolution) ──POST /webhook/whatsapp──▶ n8n
       n8n (Webhook /webhook/whatsapp)
            │
            ├─ 1. Normaliza: extrai numberId + text do payload Evolution
            │
            ├─ 2. HTTP POST https://bot/v1/turn  { wa_id, text }
            │
            ├─ 3. Itera ações no `actions` retornado
            │
            ├─ 4. Para cada ação, envia mensagem via Evolution
            │       POST https://evolution:8080/send-text/{{INSTANCE}}
            │
            └─ 5. Ack HTTP 200 ao Evolution
```

## Nós do fluxo

| Nó | Tipo | Destino |
|---|---|---|
| Webhook (IN) | `n8n-nodes-base.webhook` | Recebe o `POST` do Evolution na rota `/webhook/whatsapp`. Path coincidente com `WEBHOOK_GLOBAL_URL` do docker-compose. |
| Normaliza webhook | `n8n-nodes-base.code` | Extrai `numberId` e o texto (`message.conversation`, ou `text`). |
| Chama /v1/turn | `n8n-nodes-base.httpRequest` | `POST {{BOT_SERVICE_URL}}/v1/turn` com corpo `{ wa_id, text }`. |
| Prépara envio | `n8n-nodes-base.code` | Transforma `action` no array `{ to, text, buttons }` que a lanterna envia. |
| Itera envio | `n8n-nodes-base.iterateOverItems` | Executa um envio por ação (texto ou botões). |
| Envio via Evolution | `n8n-nodes-base.httpRequest` | `POST {{EVOLUTION_API_URL}}/send-text/{{INSTANCE}}` com o corpo preparado. |
| Ack (200) | `n8n-nodes-base.respondToWebhook` | Retorna HTTP 200 ao Evolution, dizendo que o webhook foi consumido. |

## Variáveis de ambiente no n8n

Crie-as no painel **Environments** do n8n (default):

| Variável | Valor |
|---|---|
| `BOT_SERVICE_URL` | `http://bot:8000` (interno ao Docker Compose) |
| `EVOLUTION_API_URL` | `http://evolution:8080` (interno ao Docker Compose) |
| `INSTANCE` | `default` (nome da instância do Evolution, se houver) |

## Endpoint de envio via Evolution

A lanterna chama o endpoint `send-text/{INSTANCE}` com o header `apikey`
definido pela variável `EVOLUTION_API_KEY` (no container `evolution`).

Corpo do POST (exemplo para texto):

```json
{
  "number": "5511999999999",
  "text": "Olá! O seu pacote de hotel + aéreo para Gramado está em..."
}
```

Para botões (o Evolution aceita `buttons` na mesma rota):

```json
{
  "number": "5511999999999",
  "text": "O que você prefere?",
  "buttons": [
    { "body": "🔑 Ver cotação" },
    { "body": "🛠️  Corrigir dados" }
  ]
}
```

## Teste local

Com o stack subido (`docker compose up --build -d`), exporte as variáveis no
n8n e chame:

```bash
curl -sL -X POST http://localhost:5678/webhook/whatsapp \
  -H 'Content-Type: application/json' \
  -d '{
    "numberId": "5511999999999",
    "message": { "conversation": "olá, quero hotel em Gramado 12 a 17 de setembro" },
    "messageType": "text"
  }'
```

O n8n responde com o JSON do turno (`actions`, `handoff`, `state`).

## Validar

```bash
cd bot
python -m unittest discover -s tests -v
```

Os testes já cobrem o fluxo offline; o n8n só entra em cena quando o stack
completo (`bot`, `n8n`, `evolution`, `postgres`, `redis`) está subido.
