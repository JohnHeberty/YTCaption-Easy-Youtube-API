-- =========================================================
-- Roteiros gerados (cabeçalho) + itens normalizados
-- Idempotente (pode rodar N vezes sem quebrar)
-- =========================================================

CREATE SCHEMA IF NOT EXISTS reddit;

-- -----------------------------
-- 1) Cabeçalho do roteiro
-- -----------------------------
CREATE TABLE IF NOT EXISTS reddit.video_scripts (
  script_id         BIGSERIAL PRIMARY KEY,
  post_id           TEXT NOT NULL,
  language          TEXT NOT NULL DEFAULT 'pt-BR',
  content_rating    TEXT NOT NULL DEFAULT 'Geral',
  estimated_seconds INTEGER NOT NULL CHECK (estimated_seconds > 0),
  hook              TEXT NOT NULL,
  
  -- Metadados
  model_name        TEXT,
  prompt_version    TEXT,
  generation_source TEXT,
  
  -- Status da cena
  scene_created     BOOLEAN NOT NULL DEFAULT FALSE,
  
  generated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  
  CONSTRAINT fk_video_scripts_post
    FOREIGN KEY (post_id) REFERENCES reddit.posts(post_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

COMMENT ON TABLE reddit.video_scripts IS 'Cabeçalho do roteiro gerado para vídeo (TikTok/Reels/Shorts), associado a um post do Reddit.';
COMMENT ON COLUMN reddit.video_scripts.scene_created IS
'TRUE quando o roteiro e suas cenas foram ingeridos com sucesso pela função reddit.save_video_script.';
COMMENT ON COLUMN reddit.video_scripts.script_id IS 'Identificador interno da geração do roteiro.';
COMMENT ON COLUMN reddit.video_scripts.post_id IS 'ID do post no Reddit (FK para reddit.posts).';
COMMENT ON COLUMN reddit.video_scripts.language IS 'Idioma do roteiro (ex.: pt-BR).';
COMMENT ON COLUMN reddit.video_scripts.content_rating IS 'Classificação do conteúdo (ex.: Geral).';
COMMENT ON COLUMN reddit.video_scripts.estimated_seconds IS 'Duração estimada do roteiro em segundos.';
COMMENT ON COLUMN reddit.video_scripts.hook IS 'Gancho inicial para prender atenção nos primeiros segundos.';
COMMENT ON COLUMN reddit.video_scripts.model_name IS 'Modelo utilizado na geração (opcional).';
COMMENT ON COLUMN reddit.video_scripts.prompt_version IS 'Versão do prompt usado na geração (opcional).';
COMMENT ON COLUMN reddit.video_scripts.generation_source IS 'Origem do processo de geração (opcional).';
COMMENT ON COLUMN reddit.video_scripts.generated_at IS 'Timestamp da geração do roteiro.';

-- =========================================================
-- Constraint: 1 roteiro por post (idempotente)
-- =========================================================
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint c
    JOIN pg_class t ON t.oid = c.conrelid
    JOIN pg_namespace n ON n.oid = t.relnamespace
    WHERE c.conname = 'video_scripts_one_per_post_uk'
      AND n.nspname = 'reddit'
      AND t.relname = 'video_scripts'
  ) THEN
    ALTER TABLE reddit.video_scripts
      ADD CONSTRAINT video_scripts_one_per_post_uk UNIQUE (post_id);
  END IF;
END $$;

-- =========================================================
-- Índices (idempotentes)
-- =========================================================
CREATE INDEX IF NOT EXISTS idx_video_scripts_post_generated_at
  ON reddit.video_scripts (post_id, generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_video_scripts_generated_at
  ON reddit.video_scripts (generated_at DESC);

CREATE INDEX IF NOT EXISTS idx_video_scripts_post
  ON reddit.video_scripts (post_id);

-- -----------------------------------------
-- 2) Narração
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS reddit.video_script_narration (
  script_id BIGINT NOT NULL,
  t         INTEGER NOT NULL CHECK (t >= 0),
  text      TEXT NOT NULL,

  PRIMARY KEY (script_id, t),

  CONSTRAINT fk_narration_script
    FOREIGN KEY (script_id) REFERENCES reddit.video_scripts(script_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_narration_script
  ON reddit.video_script_narration (script_id, t);

-- -----------------------------------------
-- 3) Texto na tela
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS reddit.video_script_on_screen_text (
  script_id BIGINT NOT NULL,
  t         INTEGER NOT NULL CHECK (t >= 0),
  text      TEXT NOT NULL,

  PRIMARY KEY (script_id, t, text),

  CONSTRAINT fk_on_screen_script
    FOREIGN KEY (script_id) REFERENCES reddit.video_scripts(script_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_on_screen_script
  ON reddit.video_script_on_screen_text (script_id, t);

-- -----------------------------------------
-- 4) Sugestões de cena
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS reddit.video_script_scene_suggestions (
  script_id BIGINT NOT NULL,
  t         INTEGER NOT NULL CHECK (t >= 0),
  visual    TEXT NOT NULL,

  PRIMARY KEY (script_id, t, visual),

  CONSTRAINT fk_scene_script
    FOREIGN KEY (script_id) REFERENCES reddit.video_scripts(script_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_scene_script
  ON reddit.video_script_scene_suggestions (script_id, t);

-- -----------------------------------------
-- 5) Opções de título
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS reddit.video_script_title_options (
  script_id BIGINT NOT NULL,
  idx       SMALLINT NOT NULL CHECK (idx >= 1),
  title     TEXT NOT NULL,

  PRIMARY KEY (script_id, idx),

  CONSTRAINT fk_title_options_script
    FOREIGN KEY (script_id) REFERENCES reddit.video_scripts(script_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

-- -----------------------------------------
-- 6) Hashtags
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS reddit.video_script_hashtags (
  script_id BIGINT NOT NULL,
  tag       TEXT NOT NULL,

  PRIMARY KEY (script_id, tag),

  CONSTRAINT fk_hashtags_script
    FOREIGN KEY (script_id) REFERENCES reddit.video_scripts(script_id)
    ON UPDATE CASCADE ON DELETE CASCADE,

  CONSTRAINT hashtags_format_chk CHECK (tag ~ '^#[^\\s#]+$')
);

-- -----------------------------------------
-- 7) Notas de segurança
-- -----------------------------------------
CREATE TABLE IF NOT EXISTS reddit.video_script_safety_notes (
  script_id BIGINT NOT NULL,
  idx       SMALLINT NOT NULL CHECK (idx >= 1),
  note      TEXT NOT NULL,

  PRIMARY KEY (script_id, idx),

  CONSTRAINT fk_safety_notes_script
    FOREIGN KEY (script_id) REFERENCES reddit.video_scripts(script_id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

-- =========================================================
-- View para reconstruir o payload
-- =========================================================
CREATE OR REPLACE VIEW reddit.vw_video_script_payload AS
SELECT
  vs.script_id,
  vs.post_id,
  vs.language,
  vs.content_rating,
  vs.estimated_seconds,
  vs.hook,
  (
    SELECT jsonb_agg(jsonb_build_object('t', n.t, 'text', n.text) ORDER BY n.t)
    FROM reddit.video_script_narration n
    WHERE n.script_id = vs.script_id
  ) AS narration,
  (
    SELECT jsonb_agg(jsonb_build_object('t', o.t, 'text', o.text) ORDER BY o.t)
    FROM reddit.video_script_on_screen_text o
    WHERE o.script_id = vs.script_id
  ) AS on_screen_text,
  (
    SELECT jsonb_agg(jsonb_build_object('t', s.t, 'visual', s.visual) ORDER BY s.t)
    FROM reddit.video_script_scene_suggestions s
    WHERE s.script_id = vs.script_id
  ) AS scene_suggestions,
  (
    SELECT jsonb_agg(t.title ORDER BY t.idx)
    FROM reddit.video_script_title_options t
    WHERE t.script_id = vs.script_id
  ) AS title_options,
  (
    SELECT jsonb_agg(h.tag ORDER BY h.tag)
    FROM reddit.video_script_hashtags h
    WHERE h.script_id = vs.script_id
  ) AS hashtags,
  (
    SELECT jsonb_agg(sn.note ORDER BY sn.idx)
    FROM reddit.video_script_safety_notes sn
    WHERE sn.script_id = vs.script_id
  ) AS safety_notes,
  vs.model_name,
  vs.prompt_version,
  vs.generation_source,
  vs.generated_at
FROM reddit.video_scripts vs;
