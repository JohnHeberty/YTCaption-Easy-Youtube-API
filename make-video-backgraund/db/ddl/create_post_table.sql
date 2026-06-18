-- PostgreSQL DDL (atualizado): status de publicação do mesmo post em outras redes sociais
-- Removidos: substack, whatsapp, telegram, snapchat, medium, twitter/X, linkedin, mastodon

CREATE SCHEMA IF NOT EXISTS reddit;

CREATE TABLE IF NOT EXISTS reddit.post_social_status (
  post_id TEXT PRIMARY KEY
    REFERENCES reddit.posts(post_id) ON DELETE CASCADE,  -- FK para o post (garante integridade).

  -- Flags por rede social (TRUE = já foi postado nessa rede; FALSE = ainda não)
  instagram_posted  BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no Instagram.
  facebook_posted   BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no Facebook.
  tiktok_posted     BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no TikTok.
  youtube_posted    BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no YouTube.
  threads_posted    BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no Threads.
  bluesky_posted    BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no Bluesky.
  pinterest_posted  BOOLEAN NOT NULL DEFAULT FALSE,     -- Status de publicação no Pinterest.
  kwai_posted       BOOLEAN NOT NULL DEFAULT FALSE      -- Status de publicação no Kwai.
);

COMMENT ON TABLE reddit.post_social_status IS
  'Tabela wide para controlar se o conteúdo (post_id) já foi publicado em outras redes sociais (colunas booleanas por rede).';

COMMENT ON COLUMN reddit.post_social_status.post_id IS
  'Chave primária do post (mesmo post_id da tabela reddit.posts). Também é FK para garantir integridade.';

COMMENT ON COLUMN reddit.post_social_status.instagram_posted IS 'TRUE se o post já foi publicado no Instagram.';
COMMENT ON COLUMN reddit.post_social_status.facebook_posted IS 'TRUE se o post já foi publicado no Facebook.';
COMMENT ON COLUMN reddit.post_social_status.tiktok_posted IS 'TRUE se o post já foi publicado no TikTok.';
COMMENT ON COLUMN reddit.post_social_status.youtube_posted IS 'TRUE se o post já foi publicado no YouTube.';
COMMENT ON COLUMN reddit.post_social_status.threads_posted IS 'TRUE se o post já foi publicado no Threads.';
COMMENT ON COLUMN reddit.post_social_status.bluesky_posted IS 'TRUE se o post já foi publicado no Bluesky.';
COMMENT ON COLUMN reddit.post_social_status.pinterest_posted IS 'TRUE se o post já foi publicado no Pinterest.';
COMMENT ON COLUMN reddit.post_social_status.kwai_posted IS 'TRUE se o post já foi publicado no Kwai.';

-- Índices opcionais (úteis se você fizer filtros frequentes por rede)
CREATE INDEX IF NOT EXISTS idx_post_social_status_instagram_posted ON reddit.post_social_status (instagram_posted);
CREATE INDEX IF NOT EXISTS idx_post_social_status_facebook_posted  ON reddit.post_social_status (facebook_posted);
CREATE INDEX IF NOT EXISTS idx_post_social_status_tiktok_posted    ON reddit.post_social_status (tiktok_posted);
CREATE INDEX IF NOT EXISTS idx_post_social_status_youtube_posted   ON reddit.post_social_status (youtube_posted);
