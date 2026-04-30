import pytest


@pytest.mark.unit
class TestSearchRoutes:
    def test_video_info_missing_body(self, client):
        response = client.post("/search/video-info", json={})
        assert response.status_code == 422