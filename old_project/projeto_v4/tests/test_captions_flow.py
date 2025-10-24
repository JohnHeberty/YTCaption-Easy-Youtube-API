from fastapi.testclient import TestClient


def test_cached_only_flow(tmp_path, monkeypatch):
    # Força modo cached-only e diretório isolado
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CACHED_ONLY", "true")

    # Recria app com novas settings
    from importlib import reload
    import projeto_v3.app.main as main_mod
    reload(main_mod)
    client = TestClient(main_mod.app)

    video_id = "abc123"

    # Cache miss
    r = client.get(f"/captions/{video_id}/cached")
    assert r.status_code == 404

    # Semeia o cache manualmente
    from projeto_v3.infrastructure.cache import FileCaptionCache
    from projeto_v3.domain.entities import VideoCaptions, CaptionLine
    cache = FileCaptionCache(str(tmp_path))
    cache.put(VideoCaptions(video_id=video_id, lines=[CaptionLine(0, 1, "oi")] ))

    # Agora GET cached deve funcionar
    r = client.get(f"/captions/{video_id}/cached")
    assert r.status_code == 200
    assert r.json()["video_id"] == video_id
    assert r.json()["lines"] == 1

    # POST salva a partir do cache
    r = client.post(f"/captions/{video_id}")
    assert r.status_code == 200
    body = r.json()
    assert body["saved_path"].endswith(f"{video_id}.txt")
