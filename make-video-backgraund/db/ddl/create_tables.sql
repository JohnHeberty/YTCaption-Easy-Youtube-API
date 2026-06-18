-- PostgreSQL DDL (recomendado) para armazenar snapshots de posts do Reddit
-- Inclui colunas “top-level” para análise + raw JSONB para auditoria/reprocessamento.

CREATE SCHEMA IF NOT EXISTS reddit;

CREATE TABLE IF NOT EXISTS reddit.posts (
  -- Identificação
  post_id             TEXT PRIMARY KEY,                -- ID curto do post (ex.: "1q51wva"). Chave primária e deduplicação.
  post_fullname       TEXT NOT NULL UNIQUE,            -- ID “fullname” (ex.: "t3_1q51wva"). Útil para integrar com APIs e garantir unicidade alternativa.
  kind                TEXT NOT NULL,                   -- Tipo do item (para posts geralmente "t3"). Ajuda a validar payloads/ETL.

  -- Contexto do subreddit
  subreddit           TEXT NOT NULL,                   -- Nome do subreddit (ex.: "RelatosDoReddit").
  subreddit_id        TEXT,                            -- ID do subreddit (ex.: "t5_72ljkj"). Útil para joins estáveis mesmo se o nome mudar.

  -- Autor (atenção a privacidade conforme seu caso de uso)
  author              TEXT,                            -- Username do autor (pode mudar/ser apagado; pode ser dado pessoal dependendo do contexto).
  author_fullname     TEXT,                            -- Fullname do autor (ex.: "t2_..."). Útil para identificar de forma mais estável que o username.

  -- Tempo (UTC em epoch seconds)
  created_utc         BIGINT NOT NULL,                 -- Timestamp de criação do post (epoch em segundos UTC).
  created_at          TIMESTAMPTZ GENERATED ALWAYS AS
                     (to_timestamp(created_utc)) STORED, -- Mesmo timestamp, mas convertido para TIMESTAMPTZ (facilita queries/particionamento por data).

  edited              BOOLEAN NOT NULL DEFAULT FALSE,   -- Indica se o post foi editado (no Reddit pode ser bool ou timestamp; aqui você está usando bool).

  ingested_at         BIGINT NOT NULL,                 -- Timestamp de ingestão/coleta (epoch em segundos UTC). Essencial para rastrear “quando eu vi esse estado”.
  ingested_at_ts      TIMESTAMPTZ GENERATED ALWAYS AS
                     (to_timestamp(ingested_at)) STORED, -- Mesmo timestamp convertido para TIMESTAMPTZ.

  -- Conteúdo e classificação
  title               TEXT,                            -- Título do post.
  selftext            TEXT,                            -- Corpo do post (texto). Base para NLP, full-text search, etc.
  flair_text          TEXT,                            -- Texto do flair (categoria/rotulagem do subreddit), quando existir.

  -- Métricas (snapshot no momento da coleta)
  score               INTEGER,                         -- Score do post no snapshot (pode variar ao longo do tempo).
  ups                 INTEGER,                         -- Upvotes (nem sempre confiável em todas as APIs; manter como snapshot do payload).
  upvote_ratio        NUMERIC(5,4),                    -- Razão de upvotes (0..1). NUMERIC para evitar ruído de float.
  num_comments        INTEGER,                         -- Número de comentários (snapshot).
  total_awards_received INTEGER,                       -- Total de awards recebidos (snapshot).

  -- Flags de estado/moderação/visibilidade
  over_18             BOOLEAN,                         -- NSFW.
  spoiler             BOOLEAN,                         -- Marcado como spoiler.
  locked              BOOLEAN,                         -- Comentários travados (sem novos comentários).
  archived            BOOLEAN,                         -- Arquivado (restrições de interação dependendo de regras).
  stickied            BOOLEAN,                         -- Fixado (sticky) no subreddit.
  pinned              BOOLEAN,                         -- “Pinned” (campo aparece em alguns payloads; manter como sinal adicional).
  quarantine          BOOLEAN,                         -- Subreddit/quarentena (restrições extras).

  -- Navegação / links
  permalink           TEXT,                            -- Caminho relativo do post (útil para construir URL e rastrear rotas).
  url                 TEXT,                            -- URL completa do post.
  domain              TEXT,                            -- Domínio do post (ex.: "self.<subreddit>" para posts de texto; ou domínio externo em links).

  -- Raw payload para auditoria e evolução de schema
  raw                 JSONB NOT NULL,                  -- JSON original (ou minimamente transformado) para reprocessar e extrair novos campos no futuro.

  -- Restrições de qualidade
  CONSTRAINT posts_kind_chk CHECK (kind = 't3'),       -- Esta tabela está modelada para posts; garante consistência.
  CONSTRAINT posts_upvote_ratio_chk CHECK (
    upvote_ratio IS NULL OR (upvote_ratio >= 0 AND upvote_ratio <= 1)
  )
);

COMMENT ON TABLE reddit.posts IS
  'Tabela de posts do Reddit (snapshot): colunas normalizadas para análise + raw JSONB para auditoria/reprocessamento.';

-- Comentários por coluna (documentação no catálogo do Postgres)
COMMENT ON COLUMN reddit.posts.post_id IS 'ID curto do post (ex.: "1q51wva"). Chave primária para deduplicação.';
COMMENT ON COLUMN reddit.posts.post_fullname IS 'Fullname do post (ex.: "t3_1q51wva"). Identificador canônico em APIs.';
COMMENT ON COLUMN reddit.posts.kind IS 'Tipo do item no Reddit. Para posts, normalmente "t3".';

COMMENT ON COLUMN reddit.posts.subreddit IS 'Nome do subreddit no snapshot (ex.: "RelatosDoReddit").';
COMMENT ON COLUMN reddit.posts.subreddit_id IS 'ID do subreddit (ex.: "t5_..."), mais estável que o nome.';

COMMENT ON COLUMN reddit.posts.author IS 'Username do autor no snapshot (pode ser removido/mudar; avalie privacidade).';
COMMENT ON COLUMN reddit.posts.author_fullname IS 'Fullname do autor (ex.: "t2_..."), útil como identificador estável.';

COMMENT ON COLUMN reddit.posts.created_utc IS 'Epoch seconds (UTC) da criação do post.';
COMMENT ON COLUMN reddit.posts.created_at IS 'created_utc convertido para TIMESTAMPTZ (gerado automaticamente).';

COMMENT ON COLUMN reddit.posts.edited IS 'Indica se o post foi editado (modelo boolean para seu pipeline).';

COMMENT ON COLUMN reddit.posts.ingested_at IS 'Epoch seconds (UTC) do momento da ingestão/coleta.';
COMMENT ON COLUMN reddit.posts.ingested_at_ts IS 'ingested_at convertido para TIMESTAMPTZ (gerado automaticamente).';

COMMENT ON COLUMN reddit.posts.title IS 'Título do post.';
COMMENT ON COLUMN reddit.posts.selftext IS 'Texto do post (conteúdo principal).';
COMMENT ON COLUMN reddit.posts.flair_text IS 'Texto do flair do post (categoria/rotulagem do subreddit).';

COMMENT ON COLUMN reddit.posts.score IS 'Score do post no momento do snapshot.';
COMMENT ON COLUMN reddit.posts.ups IS 'Upvotes no snapshot (pode variar conforme endpoint/payload).';
COMMENT ON COLUMN reddit.posts.upvote_ratio IS 'Razão de upvotes (0..1) no snapshot.';
COMMENT ON COLUMN reddit.posts.num_comments IS 'Quantidade de comentários no snapshot.';
COMMENT ON COLUMN reddit.posts.total_awards_received IS 'Total de awards recebidos no snapshot.';

COMMENT ON COLUMN reddit.posts.over_18 IS 'Flag NSFW.';
COMMENT ON COLUMN reddit.posts.spoiler IS 'Flag de spoiler.';
COMMENT ON COLUMN reddit.posts.locked IS 'Post travado para novos comentários.';
COMMENT ON COLUMN reddit.posts.archived IS 'Post arquivado (restrições podem se aplicar).';
COMMENT ON COLUMN reddit.posts.stickied IS 'Post fixado (sticky) no subreddit.';
COMMENT ON COLUMN reddit.posts.pinned IS 'Flag pinned (quando presente no payload).';
COMMENT ON COLUMN reddit.posts.quarantine IS 'Flag de quarentena do subreddit/post (quando aplicável).';

COMMENT ON COLUMN reddit.posts.permalink IS 'Permalink relativo (caminho) do post.';
COMMENT ON COLUMN reddit.posts.url IS 'URL absoluta do post.';
COMMENT ON COLUMN reddit.posts.domain IS 'Domínio do post (self.<subreddit> ou domínio externo).';

COMMENT ON COLUMN reddit.posts.raw IS 'Payload JSONB original para auditoria e extrações futuras (schema evolution).';

-- Índices recomendados para consultas comuns
CREATE INDEX IF NOT EXISTS idx_posts_subreddit_created_utc
  ON reddit.posts (subreddit, created_utc DESC);

CREATE INDEX IF NOT EXISTS idx_posts_author_created_utc
  ON reddit.posts (author, created_utc DESC);

CREATE INDEX IF NOT EXISTS idx_posts_ingested_at
  ON reddit.posts (ingested_at DESC);

-- Index para consultas dentro do JSONB (use com parcimônia; ótimo quando você consulta caminhos do raw)
CREATE INDEX IF NOT EXISTS idx_posts_raw_gin
  ON reddit.posts USING GIN (raw);

-- (Opcional) Full-text search em PT-BR: título + corpo
-- Requer que você use consultas com @@ e to_tsquery/plainto_tsquery.
CREATE INDEX IF NOT EXISTS idx_posts_fts
  ON reddit.posts USING GIN (to_tsvector('portuguese', coalesce(title,'') || ' ' || coalesce(selftext,'')));
