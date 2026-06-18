CREATE OR REPLACE FUNCTION reddit.save_video_script(
  p_payload           jsonb,
  p_model_name        text DEFAULT NULL,
  p_prompt_version    text DEFAULT NULL,
  p_generation_source text DEFAULT NULL
)
RETURNS bigint
LANGUAGE plpgsql
AS $$
DECLARE
  v_post_id   text;
  v_script_id bigint;
  v_hook      text;
  v_est_secs  integer;
BEGIN
  -- =====================
  -- Validações mínimas
  -- =====================
  v_post_id := NULLIF(trim(p_payload->>'post_id'), '');
  IF v_post_id IS NULL THEN
    RAISE EXCEPTION 'payload.post_id is required';
  END IF;

  v_hook := NULLIF(trim(p_payload->>'hook'), '');
  IF v_hook IS NULL THEN
    RAISE EXCEPTION 'payload.hook is required';
  END IF;

  v_est_secs := NULLIF((p_payload->>'estimated_seconds')::int, 0);
  IF v_est_secs IS NULL OR v_est_secs <= 0 THEN
    RAISE EXCEPTION 'payload.estimated_seconds must be a positive integer';
  END IF;

  -- Evita corrida por post_id
  PERFORM pg_advisory_xact_lock(hashtext(v_post_id)::bigint);

  -- =====================
  -- Garante 1 roteiro por post
  -- =====================
  DELETE FROM reddit.video_scripts
  WHERE post_id = v_post_id;

  -- =====================
  -- Insere cabeçalho (scene_created = TRUE)
  -- =====================
  INSERT INTO reddit.video_scripts (
    post_id,
    language,
    content_rating,
    estimated_seconds,
    hook,
    model_name,
    prompt_version,
    generation_source,
    scene_created
  )
  VALUES (
    v_post_id,
    COALESCE(NULLIF(trim(p_payload->>'language'), ''), 'pt-BR'),
    COALESCE(NULLIF(trim(p_payload->>'content_rating'), ''), 'Geral'),
    v_est_secs,
    v_hook,
    p_model_name,
    p_prompt_version,
    p_generation_source,
    TRUE
  )
  RETURNING script_id INTO v_script_id;

  -- =====================
  -- Narração
  -- =====================
  IF jsonb_typeof(p_payload->'narration') = 'array' THEN
    INSERT INTO reddit.video_script_narration (script_id, t, text)
    SELECT
      v_script_id,
      GREATEST(0, COALESCE((e->>'t')::int, 0)),
      e->>'text'
    FROM jsonb_array_elements(p_payload->'narration') AS e
    WHERE NULLIF(trim(e->>'text'), '') IS NOT NULL;
  END IF;

  -- =====================
  -- Texto na tela
  -- =====================
  IF jsonb_typeof(p_payload->'on_screen_text') = 'array' THEN
    INSERT INTO reddit.video_script_on_screen_text (script_id, t, text)
    SELECT
      v_script_id,
      GREATEST(0, COALESCE((e->>'t')::int, 0)),
      e->>'text'
    FROM jsonb_array_elements(p_payload->'on_screen_text') AS e
    WHERE NULLIF(trim(e->>'text'), '') IS NOT NULL;
  END IF;

  -- =====================
  -- Cenas
  -- =====================
  IF jsonb_typeof(p_payload->'scene_suggestions') = 'array' THEN
    INSERT INTO reddit.video_script_scene_suggestions (script_id, t, visual)
    SELECT
      v_script_id,
      GREATEST(0, COALESCE((e->>'t')::int, 0)),
      COALESCE(NULLIF(trim(e->>'visual'), ''), NULLIF(trim(e->>'text'), ''))
    FROM jsonb_array_elements(p_payload->'scene_suggestions') AS e
    WHERE COALESCE(NULLIF(trim(e->>'visual'), ''), NULLIF(trim(e->>'text'), '')) IS NOT NULL;
  END IF;

  -- =====================
  -- Títulos
  -- =====================
  IF jsonb_typeof(p_payload->'title_options') = 'array' THEN
    INSERT INTO reddit.video_script_title_options (script_id, idx, title)
    SELECT
      v_script_id,
      ord::smallint,
      val
    FROM jsonb_array_elements_text(p_payload->'title_options')
         WITH ORDINALITY AS t(val, ord)
    WHERE NULLIF(trim(val), '') IS NOT NULL;
  END IF;

  -- =====================
  -- Hashtags
  -- =====================
  IF jsonb_typeof(p_payload->'hashtags') = 'array' THEN
    INSERT INTO reddit.video_script_hashtags (script_id, tag)
    SELECT
      v_script_id,
      '#' || regexp_replace(lower(trim(val)), '^#+', '')
    FROM jsonb_array_elements_text(p_payload->'hashtags') AS t(val)
    WHERE regexp_replace(val, '\s+', '', 'g') <> '';
  END IF;

  -- =====================
  -- Safety notes
  -- =====================
  IF jsonb_typeof(p_payload->'safety_notes') = 'array' THEN
    INSERT INTO reddit.video_script_safety_notes (script_id, idx, note)
    SELECT
      v_script_id,
      ord::smallint,
      val
    FROM jsonb_array_elements_text(p_payload->'safety_notes')
         WITH ORDINALITY AS t(val, ord)
    WHERE NULLIF(trim(val), '') IS NOT NULL;

  ELSIF jsonb_typeof(p_payload->'safety_notes') = 'string' THEN
    INSERT INTO reddit.video_script_safety_notes (script_id, idx, note)
    VALUES (v_script_id, 1, p_payload->>'safety_notes');
  END IF;

  RETURN v_script_id;
END;
$$;
