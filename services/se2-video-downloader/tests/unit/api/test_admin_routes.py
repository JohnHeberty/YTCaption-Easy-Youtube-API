import pytest


@pytest.mark.unit
class TestAdminRoutes:
    def test_stats_returns_200(self, client):
        response = client.get("/admin/stats")
        assert response.status_code == 200

    def test_queue_returns_200(self, client):
        response = client.get("/admin/queue")
        assert response.status_code == 200