# Credenciais — BOT_VIAGENS

Este documento explica **de onde vem cada valor** que precisa estar no `.env`
(e qual não arriscar de subir ao Git).

> Resumo executivo: o stack usa (i) Infotravel para cotação, (ii) Evolution API
> para gateway WhatsApp, (iii) n8n para orquestração, (iv) OpenAI/Anthropic
> opcional só para extração de slots.

---

## 1. Variáveis que você define (e o que usar)

| Variável | Para quê | Como pega? | Cuidado |
|---|---|---|---|
| `POSTGRES_USER` | usuário do Postgres | você | — |
| `POSTGRES_PASSWORD` | senha do Postgres | você | não usar `postgres` como superusuário; senha forte |
| `POSTGRES_DB` | banco | você | — |
| `N8N_ENCRYPTION_KEY` | criptografa credenciais/cookies do n8n | `openssl rand -hex 32` | **seu fluxo não funciona** se mudar de máquina e o n8n não for resetado; mantenha o mesmo valor |
| `EVOLUTION_API_KEY` | chave API do gateway Evolution | `atendai` / time de operações | obrigatória para os endpoints que enviam resposta por WhatsApp |
| `INFOTRAVEL_ENV` | `homologacao` ou `producao` | você | — |
| `INFOTRAVEL_DOMAIN` | domínio do Infotravel (`.infotravel.com.br`) | **Infotravel** via portal do cliente | ex.: `seu-cliente.infotravel.com.br` |
| `INFOTRAVEL_USERNAME` | usuário da conta Infotravel | **Infotravel** | login do cliente |
| `INFOTRAVEL_PASSWORD` | senha do usuário Infotravel | **Infotravel** | trocar a senha padrão logo depois |
| `INFOTRAVEL_CLIENT` | código do cliente | **Infotravel** | só o número/client_code que o painel mostra |
| `INFOTRAVEL_AGENCY` | agência/poderes | **Infotravel** | geralmente `2` para a agência padrão; confirmar com o suporte |
| `LLM_PROVIDER` | `openai` ou `gemini` | você | só gera custo; o bot funciona sem |
| `LLM_MODEL` | modelo de LLM | você | — |
| `LLM_API_KEY` | chave de acesso ao LLM | openai/gemini | deixar em branco desativa a LLM |

---

## 2. Como obter as credenciais do Infotravel

1. Entre no portal de administração da **INFOTERA** (ou de quem administra o
   seu canal).
2. Crie/verify o **cliente** e tenha o **domínio** da API (ex.: `minhaempresa.infotravel.com.br`).
3. Crie o **usuário** e a **senha** (mudar a senha padrão no go-live).
4. No menu **“Autenticação / Clientes”**, note o `client` e o `agency` que o
   bot usará nos `Authorization` básico (`HTTP Basic`) ou no corpo
   (`client_id/client_secret`).
5. Confirme no **portal do fornecedor** se `checkRate/budget` está habilitado
   para o seu ambiente (homologação vs. produção).

> Se não tiver acesso, peça ao fornecedor a trio `domínio + usuário + senha +
> client + agency`. O repositório não expõe esses valores.

---

## 3. Evolução API (gateway WhatsApp)

- `EVOLUTION_API_KEY`: a **Authentication API Key** que o Evolution exige nas
  chamadas de envio de mensagem. Geralmente é gerada no dashboard do canal.
- O n8n chama `/send-text/{{INSTANCE}}` com esse header `apikey` (ou
  `Authorization: Bearer`).
- `BOT_SERVICE_URL` e `EVOLUTION_API_URL` no n8n são **endpoints internos do
  Docker Compose** (`http://bot:8000` e `http://evolution:8080`) e não devem
  ficar no `.env` se o n8n usar seus próprios ambientes.

---

## 4. Geração segura

```bash
# N8N_ENCRYPTION_KEY
openssl rand -hex 32

# EVOLUTION_API_KEY (se for gerar no dashboard, usar a seção "API Keys")
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Validação rápida

Assim que `.env` estiverem preenchidos:

```bash
cd bot
docker compose up --build -d
curl -s http://localhost:8000/health
```

Caso o Postgres/Redis demorem a inicializar, o bot aguarda o *healthcheck*
dos serviços (`depends_on: condition: service_healthy`).

---

## 6. Don't deploy secrets

`.env` e `n8n_data/` são `.gitignore`nados. Nunca faça *commit* desses arquivos.
