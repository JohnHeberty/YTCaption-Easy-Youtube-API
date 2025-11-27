"""
Tests for RVC Model Management API Endpoints
Sprint 7: TDD Phase 1 (Red) - Define API Contract
"""
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
import io


@pytest.fixture
def mock_rvc_model_manager():
    """Mock RvcModelManager for testing endpoints without filesystem"""
    manager = MagicMock()
    manager.storage_dir = Path("/tmp/test_rvc_models")
    return manager


@pytest.fixture
def client_with_mock_manager(mock_rvc_model_manager):
    """FastAPI test client with mocked RvcModelManager"""
    from app.main import app, processor
    
    # Inject mock manager
    processor.rvc_model_manager = mock_rvc_model_manager
    
    client = TestClient(app)
    yield client
    
    # Cleanup
    processor.rvc_model_manager = None


@pytest.fixture
def sample_pth_file():
    """Create a minimal fake .pth file for testing"""
    content = b"fake pytorch checkpoint data"
    return ("model.pth", io.BytesIO(content), "application/octet-stream")


@pytest.fixture
def sample_index_file():
    """Create a minimal fake .index file for testing"""
    content = b"fake faiss index data"
    return ("model.index", io.BytesIO(content), "application/octet-stream")


class TestRvcModelsUploadEndpoint:
    """Tests for POST /rvc-models endpoint"""
    
    def test_upload_model_success(self, client_with_mock_manager, mock_rvc_model_manager, sample_pth_file, sample_index_file):
        """Should upload RVC model with both .pth and .index files"""
        # Arrange
        expected_model = {
            "id": "abc123",
            "name": "Female Voice",
            "description": "Natural female voice",
            "pth_file": "/app/models/rvc/abc123.pth",
            "index_file": "/app/models/rvc/abc123.index",
            "created_at": "2025-11-27T10:00:00Z",
            "file_size_mb": 25.5
        }
        mock_rvc_model_manager.upload_model.return_value = expected_model
        
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            data={
                "name": "Female Voice",
                "description": "Natural female voice"
            },
            files={
                "pth_file": sample_pth_file,
                "index_file": sample_index_file
            }
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "abc123"
        assert data["name"] == "Female Voice"
        assert "pth_file" in data
        assert "index_file" in data
        
        # Verify manager was called
        mock_rvc_model_manager.upload_model.assert_called_once()
    
    def test_upload_model_without_index(self, client_with_mock_manager, mock_rvc_model_manager, sample_pth_file):
        """Should upload RVC model with only .pth file (index optional)"""
        # Arrange
        expected_model = {
            "id": "def456",
            "name": "Male Voice",
            "description": None,
            "pth_file": "/app/models/rvc/def456.pth",
            "index_file": None,
            "created_at": "2025-11-27T10:00:00Z",
            "file_size_mb": 20.0
        }
        mock_rvc_model_manager.upload_model.return_value = expected_model
        
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            data={"name": "Male Voice"},
            files={"pth_file": sample_pth_file}
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "def456"
        assert data["index_file"] is None
    
    def test_upload_model_missing_pth_file(self, client_with_mock_manager):
        """Should return 400 if .pth file is missing"""
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            data={"name": "Test Voice"}
        )
        
        # Assert
        assert response.status_code == 422  # FastAPI validation error
        assert "pth_file" in response.text.lower() or "field required" in response.text.lower()
    
    def test_upload_model_missing_name(self, client_with_mock_manager, sample_pth_file):
        """Should return 400 if name is missing"""
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            files={"pth_file": sample_pth_file}
        )
        
        # Assert
        assert response.status_code == 422
        assert "name" in response.text.lower() or "field required" in response.text.lower()
    
    def test_upload_model_invalid_pth_file(self, client_with_mock_manager, mock_rvc_model_manager, sample_pth_file):
        """Should return 400 if .pth file validation fails"""
        # Arrange
        mock_rvc_model_manager.upload_model.side_effect = ValueError("Invalid PyTorch checkpoint")
        
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            data={"name": "Bad Model"},
            files={"pth_file": sample_pth_file}
        )
        
        # Assert
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()
    
    def test_upload_model_duplicate_name(self, client_with_mock_manager, mock_rvc_model_manager, sample_pth_file):
        """Should return 409 if model name already exists"""
        # Arrange
        mock_rvc_model_manager.upload_model.side_effect = FileExistsError("Model 'Female Voice' already exists")
        
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            data={"name": "Female Voice"},
            files={"pth_file": sample_pth_file}
        )
        
        # Assert
        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]


class TestRvcModelsListEndpoint:
    """Tests for GET /rvc-models endpoint"""
    
    def test_list_models_empty(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return empty list when no models exist"""
        # Arrange
        mock_rvc_model_manager.list_models.return_value = []
        
        # Act
        response = client_with_mock_manager.get("/rvc-models")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["models"] == []
    
    def test_list_models_with_data(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return list of models when they exist"""
        # Arrange
        mock_models = [
            {
                "id": "abc123",
                "name": "Female Voice",
                "description": "Natural female",
                "pth_file": "/app/models/rvc/abc123.pth",
                "index_file": "/app/models/rvc/abc123.index",
                "created_at": "2025-11-27T10:00:00Z",
                "file_size_mb": 25.5
            },
            {
                "id": "def456",
                "name": "Male Voice",
                "description": None,
                "pth_file": "/app/models/rvc/def456.pth",
                "index_file": None,
                "created_at": "2025-11-27T11:00:00Z",
                "file_size_mb": 20.0
            }
        ]
        mock_rvc_model_manager.list_models.return_value = mock_models
        
        # Act
        response = client_with_mock_manager.get("/rvc-models")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["models"]) == 2
        assert data["models"][0]["name"] == "Female Voice"
        assert data["models"][1]["name"] == "Male Voice"
    
    def test_list_models_sorting_by_name(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should support sorting by name"""
        # Arrange
        mock_rvc_model_manager.list_models.return_value = []
        
        # Act
        response = client_with_mock_manager.get("/rvc-models?sort_by=name")
        
        # Assert
        assert response.status_code == 200
        mock_rvc_model_manager.list_models.assert_called_once_with(sort_by="name")
    
    def test_list_models_sorting_by_created_at(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should support sorting by created_at"""
        # Arrange
        mock_rvc_model_manager.list_models.return_value = []
        
        # Act
        response = client_with_mock_manager.get("/rvc-models?sort_by=created_at")
        
        # Assert
        assert response.status_code == 200
        mock_rvc_model_manager.list_models.assert_called_once_with(sort_by="created_at")


class TestRvcModelsGetEndpoint:
    """Tests for GET /rvc-models/{id} endpoint"""
    
    def test_get_model_success(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return model details when model exists"""
        # Arrange
        expected_model = {
            "id": "abc123",
            "name": "Female Voice",
            "description": "Natural female voice",
            "pth_file": "/app/models/rvc/abc123.pth",
            "index_file": "/app/models/rvc/abc123.index",
            "created_at": "2025-11-27T10:00:00Z",
            "file_size_mb": 25.5
        }
        mock_rvc_model_manager.get_model.return_value = expected_model
        
        # Act
        response = client_with_mock_manager.get("/rvc-models/abc123")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "abc123"
        assert data["name"] == "Female Voice"
        
        # Verify manager was called with correct ID
        mock_rvc_model_manager.get_model.assert_called_once_with("abc123")
    
    def test_get_model_not_found(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return 404 when model doesn't exist"""
        # Arrange
        mock_rvc_model_manager.get_model.return_value = None
        
        # Act
        response = client_with_mock_manager.get("/rvc-models/nonexistent")
        
        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestRvcModelsDeleteEndpoint:
    """Tests for DELETE /rvc-models/{id} endpoint"""
    
    def test_delete_model_success(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should delete model and return success message"""
        # Arrange
        mock_rvc_model_manager.delete_model.return_value = True
        
        # Act
        response = client_with_mock_manager.delete("/rvc-models/abc123")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "RVC model deleted"
        assert data["model_id"] == "abc123"
        
        # Verify manager was called
        mock_rvc_model_manager.delete_model.assert_called_once_with("abc123")
    
    def test_delete_model_not_found(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return 404 when model doesn't exist"""
        # Arrange
        mock_rvc_model_manager.delete_model.side_effect = FileNotFoundError("Model not found")
        
        # Act
        response = client_with_mock_manager.delete("/rvc-models/nonexistent")
        
        # Assert
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestJobsEndpointRvcIntegration:
    """Tests for POST /jobs endpoint with RVC parameters"""
    
    def test_create_job_with_rvc_enabled(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should create job with RVC parameters when enable_rvc=True"""
        # Arrange
        mock_rvc_model_manager.get_model.return_value = {
            "id": "abc123",
            "name": "Female Voice",
            "pth_file": "/app/models/rvc/abc123.pth",
            "index_file": "/app/models/rvc/abc123.index"
        }
        
        # Act
        response = client_with_mock_manager.post(
            "/jobs",
            data={
                "text": "Hello world",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": "abc123",
                "rvc_pitch": "0",
                "rvc_index_rate": "0.75"
            }
        )
        
        # Assert
        assert response.status_code in [200, 201, 202]
        data = response.json()
        
        # Should have RVC fields populated
        if "enable_rvc" in data:
            assert data["enable_rvc"] is True
        if "rvc_model_id" in data:
            assert data["rvc_model_id"] == "abc123"
    
    def test_create_job_without_rvc(self, client_with_mock_manager):
        """Should create job with RVC disabled by default"""
        # Act
        response = client_with_mock_manager.post(
            "/jobs",
            data={
                "text": "Hello world",
                "source_language": "en",
                "mode": "dubbing"
            }
        )
        
        # Assert
        assert response.status_code in [200, 201, 202]
        data = response.json()
        
        # RVC should be disabled or not present
        if "enable_rvc" in data:
            assert data["enable_rvc"] is False
    
    def test_create_job_with_invalid_rvc_model(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return 404 when RVC model doesn't exist"""
        # Arrange
        mock_rvc_model_manager.get_model.return_value = None
        
        # Act
        response = client_with_mock_manager.post(
            "/jobs",
            data={
                "text": "Hello world",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true",
                "rvc_model_id": "nonexistent"
            }
        )
        
        # Assert
        assert response.status_code == 404
        assert "model" in response.json()["detail"].lower()
    
    def test_create_job_rvc_enabled_without_model_id(self, client_with_mock_manager):
        """Should return 400 when RVC enabled but model_id missing"""
        # Act
        response = client_with_mock_manager.post(
            "/jobs",
            data={
                "text": "Hello world",
                "source_language": "en",
                "mode": "dubbing",
                "enable_rvc": "true"
            }
        )
        
        # Assert
        assert response.status_code == 400
        assert "model" in response.json()["detail"].lower() or "required" in response.json()["detail"].lower()


class TestRvcModelsStatsEndpoint:
    """Tests for GET /rvc-models/stats endpoint (optional)"""
    
    def test_get_stats(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return statistics about RVC models"""
        # Arrange
        mock_rvc_model_manager.get_model_stats.return_value = {
            "total_models": 5,
            "total_size_mb": 125.5,
            "models_with_index": 3,
            "models_without_index": 2
        }
        
        # Act
        response = client_with_mock_manager.get("/rvc-models/stats")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["total_models"] == 5
        assert data["total_size_mb"] == 125.5


class TestRvcEndpointsErrorHandling:
    """Tests for error handling across RVC endpoints"""
    
    def test_upload_file_too_large(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return 413 when file exceeds size limit"""
        # Arrange
        large_file = ("model.pth", io.BytesIO(b"x" * (100 * 1024 * 1024)), "application/octet-stream")  # 100MB
        mock_rvc_model_manager.upload_model.side_effect = ValueError("File too large")
        
        # Act
        response = client_with_mock_manager.post(
            "/rvc-models",
            data={"name": "Large Model"},
            files={"pth_file": large_file}
        )
        
        # Assert
        assert response.status_code in [400, 413]
    
    def test_internal_server_error(self, client_with_mock_manager, mock_rvc_model_manager):
        """Should return 500 when unexpected error occurs"""
        # Arrange
        mock_rvc_model_manager.list_models.side_effect = RuntimeError("Database connection failed")
        
        # Act
        response = client_with_mock_manager.get("/rvc-models")
        
        # Assert
        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower() or "detail" in response.json()


class TestRvcEndpointsIntegration:
    """Integration tests for complete RVC workflow"""
    
    def test_full_workflow_upload_list_get_delete(self, client_with_mock_manager, mock_rvc_model_manager, sample_pth_file):
        """Should support complete CRUD workflow"""
        # Setup mock responses
        uploaded_model = {
            "id": "test123",
            "name": "Test Voice",
            "pth_file": "/app/models/rvc/test123.pth",
            "created_at": "2025-11-27T10:00:00Z",
            "file_size_mb": 20.0
        }
        
        mock_rvc_model_manager.upload_model.return_value = uploaded_model
        mock_rvc_model_manager.list_models.return_value = [uploaded_model]
        mock_rvc_model_manager.get_model.return_value = uploaded_model
        mock_rvc_model_manager.delete_model.return_value = True
        
        # 1. Upload
        upload_response = client_with_mock_manager.post(
            "/rvc-models",
            data={"name": "Test Voice"},
            files={"pth_file": sample_pth_file}
        )
        assert upload_response.status_code == 201
        model_id = upload_response.json()["id"]
        
        # 2. List
        list_response = client_with_mock_manager.get("/rvc-models")
        assert list_response.status_code == 200
        assert len(list_response.json()["models"]) == 1
        
        # 3. Get
        get_response = client_with_mock_manager.get(f"/rvc-models/{model_id}")
        assert get_response.status_code == 200
        assert get_response.json()["id"] == model_id
        
        # 4. Delete
        delete_response = client_with_mock_manager.delete(f"/rvc-models/{model_id}")
        assert delete_response.status_code == 200
