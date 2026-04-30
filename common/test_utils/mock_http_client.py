"""
Mock HTTP client using respx for testing.

Usage in conftest.py:
    from common.test_utils.mock_http_client import MockHTTPClient

    @pytest.fixture
    def mock_http():
        with MockHTTPClient.mock_microservices() as mock:
            yield mock
"""
try:
    import respx
    import httpx

    class MockHTTPClient:
        """Wrapper around respx for mocking HTTP clients."""

        @staticmethod
        def mock_service(base_url, routes=None):
            """Create a mock for a specific service.

            Args:
                base_url: Base URL of the service to mock
                routes: Dict of {path: response_json} to configure

            Returns:
                respx.MockTransport context manager
            """
            def _mock():
                with respx.mock(base_url=base_url) as mock:
                    if routes:
                        for path, response in routes.items():
                            mock.get(path).respond(json=response)
                    yield mock
            return _mock()

        @staticmethod
        def mock_microservices():
            """Mock all microservice endpoints.

            Returns:
                respx route group for all services
            """
            return respx.mock(assert_all_called=False)

except ImportError:
    class MockHTTPClient:
        """Fallback when respx is not installed."""

        @staticmethod
        def mock_service(base_url, routes=None):
            from unittest.mock import MagicMock
            return MagicMock()

        @staticmethod
        def mock_microservices():
            from unittest.mock import MagicMock
            return MagicMock()