CREATE OR REPLACE VIEW reddit.vw_stories_publishable AS
WITH base AS (
  SELECT
    p.*,
    -- Normaliza o texto: colapsa espaços/quebras de linha e remove extremos.
    NULLIF(
      trim(regexp_replace(coalesce(p.selftext, ''), '\s+', ' ', 'g')),
      ''
    ) AS clean_selftext
  FROM reddit.posts p
)
SELECT
  b.post_id,
  b.post_fullname,
  b.subreddit,
  b.subreddit_id,
  b.author,
  b.author_fullname,
  b.created_at,
  b.title,
  b.selftext,
  b.flair_text,
  b.score,
  b.ups,
  b.upvote_ratio,
  b.num_comments,
  b.total_awards_received,
  b.permalink,
  b.url,
  b.domain,

  -- Métricas derivadas para decisão de publicação
  wc.word_count,
  round((wc.word_count / 150.0) * 60.0, 2) AS estimated_video_seconds,

  -- ===== NOVO: status da cena =====
  COALESCE(vs.scene_created, false) AS scene_created,

  -- Status por rede social
  COALESCE(s.instagram_posted, false) AS instagram_posted,
  COALESCE(s.facebook_posted,  false) AS facebook_posted,
  COALESCE(s.tiktok_posted,    false) AS tiktok_posted,
  COALESCE(s.youtube_posted,   false) AS youtube_posted,
  COALESCE(s.threads_posted,   false) AS threads_posted,
  COALESCE(s.bluesky_posted,   false) AS bluesky_posted,
  COALESCE(s.pinterest_posted, false) AS pinterest_posted,
  COALESCE(s.kwai_posted,      false) AS kwai_posted

FROM base b

-- Status de publicação
LEFT JOIN reddit.post_social_status s
  ON s.post_id = b.post_id

-- Status da cena (1 roteiro por post garantido por constraint)
LEFT JOIN reddit.video_scripts vs
  ON vs.post_id = b.post_id

-- Contagem de palavras
CROSS JOIN LATERAL (
  SELECT
    CASE
      WHEN b.clean_selftext IS NULL THEN 0
      ELSE array_length(regexp_split_to_array(b.clean_selftext, ' '), 1)
    END AS word_count
) wc

WHERE
  -- Público geral
  COALESCE(b.over_18, false) = false
  AND COALESCE(b.spoiler, false) = false
  AND COALESCE(b.quarantine, false) = false

  -- Sem restrições operacionais
  AND COALESCE(b.locked, false) = false
  AND COALESCE(b.archived, false) = false

  -- Texto válido
  AND b.clean_selftext IS NOT NULL

  -- Duração mínima
  AND ((wc.word_count / 150.0) * 60.0) >= 60.0

  -- Ainda não postado em nenhuma rede
  AND COALESCE(s.instagram_posted, false) = false
  AND COALESCE(s.facebook_posted,  false) = false
  AND COALESCE(s.tiktok_posted,    false) = false
  AND COALESCE(s.youtube_posted,   false) = false
  AND COALESCE(s.threads_posted,   false) = false
  AND COALESCE(s.bluesky_posted,   false) = false
  AND COALESCE(s.pinterest_posted, false) = false
  AND COALESCE(s.kwai_posted,      false) = false
;

COMMENT ON VIEW reddit.vw_stories_publishable IS
'View de histórias elegíveis para publicação: público geral (não NSFW/sem spoiler/sem quarentena), sem restrição operacional (locked/archived false), com duração estimada >= 60s (150 palavras/min) e ainda não publicadas nas redes mapeadas em post_social_status.';
