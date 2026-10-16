-- =====================================================================
-- BOT_VIAGENS — schema inicial (PostgreSQL 16)
-- Camadas de memoria: historico (mensagens) + slots (sessoes.slots)
--   + perfil/cotacoes. Rode uma vez apos subir o compose:
--   docker compose exec postgres psql -U bot -d botviagens -f /docker-entrypoint-initdb.d/001_schema.sql
-- =====================================================================

CREATE TABLE IF NOT EXISTS contatos (
  id          SERIAL PRIMARY KEY,
  wa_id       TEXT UNIQUE NOT NULL,
  nome        TEXT,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessoes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  contato_id    INTEGER NOT NULL REFERENCES contatos(id) ON DELETE CASCADE,
  instance      TEXT NOT NULL DEFAULT 'default',
  canal         TEXT NOT NULL DEFAULT 'whatsapp',
  stage         TEXT NOT NULL DEFAULT 'novo',
  slots         JSONB NOT NULL DEFAULT '{}'::jsonb,
  tentativas    INTEGER NOT NULL DEFAULT 0,
  handoff       BOOLEAN NOT NULL DEFAULT FALSE,
  ultima_msg_em TIMESTAMPTZ,
  expira_em     TIMESTAMPTZ,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sessoes_contato ON sessoes (contato_id, expira_em);

CREATE TABLE IF NOT EXISTS mensagens (
  id             BIGSERIAL PRIMARY KEY,
  sessao_id      UUID NOT NULL REFERENCES sessoes(id) ON DELETE CASCADE,
  direcao        TEXT NOT NULL CHECK (direcao IN ('in','out')),
  texto          TEXT NOT NULL DEFAULT '',
  wa_message_id  TEXT UNIQUE,
  intencao       TEXT NOT NULL DEFAULT '',
  criado_em      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_mensagens_sessao ON mensagens (sessao_id, id);

CREATE TABLE IF NOT EXISTS cotacoes (
  id          BIGSERIAL PRIMARY KEY,
  sessao_id   UUID REFERENCES sessoes(id) ON DELETE SET NULL,
  contato_id  INTEGER REFERENCES contatos(id) ON DELETE SET NULL,
  parametros  JSONB NOT NULL DEFAULT '{}'::jsonb,
  resultado   JSONB NOT NULL DEFAULT '{}'::jsonb,
  total       NUMERIC(12,2),
  moeda       TEXT NOT NULL DEFAULT 'BRL',
  search_id   TEXT,
  booking_id  INTEGER,
  status      TEXT NOT NULL DEFAULT '',
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now(),
  expira_em   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS eventos_llm (
  id          BIGSERIAL PRIMARY KEY,
  sessao_id   UUID REFERENCES sessoes(id) ON DELETE SET NULL,
  modelo      TEXT NOT NULL DEFAULT '',
  tokens_in   INTEGER NOT NULL DEFAULT 0,
  tokens_out  INTEGER NOT NULL DEFAULT 0,
  latencia_ms INTEGER NOT NULL DEFAULT 0,
  criado_em   TIMESTAMPTZ NOT NULL DEFAULT now()
);
