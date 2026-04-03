"""Integration tests for the TTS sidecar FastAPI server.

Tests the FastAPI app's HTTP interface using httpx.Client (sync) with
ASGI transport. These verify route behavior, input validation, and error
handling without loading any ML models.
"""

import pytest
from pathlib import Path
from starlette.testclient import TestClient

from server import app


@pytest.fixture
def temp_data_dir(tmp_path):
    """Provide a temporary data directory for the sidecar."""
    return str(tmp_path)


@pytest.fixture
def client(temp_data_dir):
    """Create a sync test client bound to the FastAPI app with a temp data dir."""
    import server

    original_data_dir = server.DATA_DIR
    server.DATA_DIR = Path(temp_data_dir)
    server.DATA_DIR.mkdir(parents=True, exist_ok=True)

    with TestClient(app) as c:
        yield c

    server.DATA_DIR = original_data_dir


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "healthy"

    def test_health_includes_models(self, client):
        response = client.get("/health")
        data = response.json()
        assert "models" in data
        assert "whisper" in data["models"]
        assert "qwen" in data["models"]
        assert "cosyvoice" in data["models"]


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------


class TestProfileEndpoints:
    def test_list_profiles_empty(self, client):
        response = client.get("/profiles")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        assert len(response.json()) == 0

    def test_create_profile(self, client):
        response = client.post("/profiles", json={
            "name": "Test Voice",
            "language": "en",
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test Voice"
        assert data["language"] == "en"

    def test_create_and_list_profile(self, client):
        create_resp = client.post("/profiles", json={
            "name": "My Voice",
        })
        assert create_resp.status_code == 200

        list_resp = client.get("/profiles")
        assert list_resp.status_code == 200
        profiles = list_resp.json()
        assert len(profiles) == 1
        assert profiles[0]["name"] == "My Voice"

    def test_create_profile_missing_name(self, client):
        response = client.post("/profiles", json={})
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_delete_nonexistent_profile(self, client):
        response = client.delete("/profiles/nonexistent-id-12345")
        assert response.status_code == 404

    def test_create_and_delete_profile(self, client):
        create_resp = client.post("/profiles", json={"name": "Temp"})
        profile_id = create_resp.json()["id"]

        del_resp = client.delete(f"/profiles/{profile_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["ok"] is True

        list_resp = client.get("/profiles")
        assert len(list_resp.json()) == 0

    def test_path_traversal_rejected(self, client):
        """Profile ID with path traversal should be rejected."""
        response = client.delete("/profiles/../../etc/passwd")
        assert response.status_code in (400, 404, 422, 500)


# ---------------------------------------------------------------------------
# Voice conversion endpoint
# ---------------------------------------------------------------------------


class TestVoiceConvertEndpoint:
    def test_missing_fields_returns_400(self, client):
        response = client.post("/voice-convert", json={})
        assert response.status_code == 400

    def test_missing_source_audio_returns_400(self, client):
        response = client.post("/voice-convert", json={
            "profile_id": "test-profile",
            "source_audio_path": "/nonexistent/path/audio.wav",
        })
        assert response.status_code == 400

    def test_missing_profile_id_returns_400(self, client):
        response = client.post("/voice-convert", json={
            "source_audio_path": "/tmp/some-audio.wav",
        })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# YouTube extraction endpoint
# ---------------------------------------------------------------------------


class TestYouTubeExtraction:
    def test_missing_url_returns_400(self, client):
        response = client.post("/extract-youtube", json={})
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_invalid_url_rejected(self, client):
        response = client.post("/extract-youtube", json={
            "url": "https://evil.com/malicious",
        })
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_http_url_rejected(self, client):
        """Only https URLs should be accepted."""
        response = client.post("/extract-youtube", json={
            "url": "http://youtube.com/watch?v=abc123",
        })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Generation endpoints
# ---------------------------------------------------------------------------


class TestGenerateEndpoint:
    def test_missing_required_fields(self, client):
        response = client.post("/generate", json={})
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_missing_text(self, client):
        response = client.post("/generate", json={
            "profile_id": "some-profile",
        })
        assert response.status_code == 400

    def test_missing_profile_id(self, client):
        response = client.post("/generate", json={
            "text": "Hello world",
        })
        assert response.status_code == 400

    def test_generation_status_not_found(self, client):
        response = client.get("/generate/nonexistent-id/status")
        assert response.status_code == 404

    def test_audio_download_not_found(self, client):
        response = client.get("/audio/nonexistent-id")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Model status endpoint
# ---------------------------------------------------------------------------


class TestModelEndpoints:
    def test_models_status(self, client):
        response = client.get("/models/status")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert isinstance(data["models"], list)
        assert len(data["models"]) == 3

    def test_download_unknown_model(self, client):
        response = client.post("/models/download", json={
            "model_name": "nonexistent-model",
        })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Transcription endpoints
# ---------------------------------------------------------------------------


class TestTranscriptionEndpoints:
    def test_transcribe_path_missing_file(self, client):
        response = client.post("/transcribe-path", json={
            "audio_path": "/nonexistent/path/audio.wav",
        })
        assert response.status_code == 400

    def test_transcribe_path_empty(self, client):
        response = client.post("/transcribe-path", json={
            "audio_path": "",
        })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Path traversal security (S2)
# ---------------------------------------------------------------------------


class TestPathTraversalSecurity:
    """Ensure path-accepting endpoints reject traversal attacks."""

    def test_transcribe_path_traversal_rejected(self, client):
        response = client.post("/transcribe-path", json={
            "audio_path": "../../etc/passwd",
        })
        assert response.status_code == 400
        assert "error" in response.json()

    def test_transcribe_path_absolute_outside_data_dir(self, client):
        response = client.post("/transcribe-path", json={
            "audio_path": "/etc/passwd",
        })
        assert response.status_code == 400

    def test_voice_convert_traversal_rejected(self, client):
        response = client.post("/voice-convert", json={
            "profile_id": "test-profile",
            "source_audio_path": "../../../etc/passwd",
        })
        assert response.status_code == 400

    def test_sample_from_path_traversal_rejected(self, client):
        response = client.post("/profiles/test/samples/from-path", json={
            "audio_path": "/etc/passwd",
        })
        assert response.status_code == 400

    def test_null_byte_injection_rejected(self, client):
        response = client.post("/transcribe-path", json={
            "audio_path": "/tmp/safe\x00../../etc/passwd",
        })
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Happy-path tests (T5)
# ---------------------------------------------------------------------------


class TestHappyPaths:
    """Positive-flow tests for endpoints that don't need ML models."""

    def test_health_response_shape(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert isinstance(data["models"], dict)
        assert "whisper" in data["models"]
        assert "qwen" in data["models"]
        assert "cosyvoice" in data["models"]

    def test_profile_crud_lifecycle(self, client):
        """Full create → list → delete → list cycle."""
        # Create
        create_resp = client.post("/profiles", json={"name": "Lifecycle Voice", "language": "en"})
        assert create_resp.status_code == 200
        profile = create_resp.json()
        assert profile["name"] == "Lifecycle Voice"
        profile_id = profile["id"]

        # List shows the new profile
        list_resp = client.get("/profiles")
        assert list_resp.status_code == 200
        assert any(p["id"] == profile_id for p in list_resp.json())

        # Delete
        del_resp = client.delete(f"/profiles/{profile_id}")
        assert del_resp.status_code == 200

        # List no longer shows it
        list_resp2 = client.get("/profiles")
        assert not any(p["id"] == profile_id for p in list_resp2.json())

    def test_generation_status_404_shape(self, client):
        response = client.get("/generate/nonexistent-uuid/status")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_audio_download_404_shape(self, client):
        response = client.get("/audio/nonexistent-uuid")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_model_status_shape(self, client):
        response = client.get("/models/status")
        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        models = data["models"]
        assert isinstance(models, list)
        for m in models:
            assert "model_name" in m
            assert "downloaded" in m
