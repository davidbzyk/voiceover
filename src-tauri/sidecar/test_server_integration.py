"""Integration tests for the TTS sidecar FastAPI server.

Tests the FastAPI app's HTTP interface using httpx.Client (sync) with
ASGI transport. These verify route behavior, input validation, and error
handling without loading any ML models.
"""

import pytest
from pathlib import Path
from starlette.testclient import TestClient

from server import app, MODEL_REGISTRY, _LEGACY_MODEL_ALIASES


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
    # Each TestClient runs its own event loop; a queue bound to an earlier loop cannot be awaited.
    import asyncio

    server._generation_queue = asyncio.Queue(maxsize=100)

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
        assert "tts" in data["models"]
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

    def test_missing_engine_is_refused(self, client):
        response = client.post("/generate", json={"profile_id": "p", "text": "Hello"})
        assert response.status_code == 400
        assert "engine" in response.json()["error"]

    def test_unknown_engine_is_refused(self, client):
        response = client.post("/generate", json={"engine": "nope", "profile_id": "p", "text": "Hi"})
        assert response.status_code == 400

    def test_non_tts_row_is_refused_as_engine(self, client):
        response = client.post(
            "/generate", json={"engine": "whisper-medium", "profile_id": "p", "text": "Hi"}
        )
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
        assert len(data["models"]) == len(MODEL_REGISTRY)

    def test_download_unknown_model(self, client):
        response = client.post("/models/download", json={
            "model_name": "nonexistent-model",
        })
        assert response.status_code == 400

    def test_delete_unknown_model(self, client):
        """DELETE with an unknown model name should return 400."""
        response = client.delete("/models/nonexistent-model")
        assert response.status_code == 400
        data = response.json()
        assert "error" in data

    def test_delete_not_downloaded_model(self, client):
        """DELETE a valid but not-downloaded model should return 404."""
        response = client.delete("/models/whisper-large-v3-turbo")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data

    def test_delete_legacy_alias_resolves(self, client):
        """DELETE using a legacy alias should resolve and attempt deletion."""
        response = client.delete("/models/whisper")
        # Should resolve to whisper-large-v3-turbo and return 404 (not downloaded)
        assert response.status_code == 404


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

    def test_transcription_runs_on_the_mlx_thread(self, client, temp_data_dir, monkeypatch):
        """Whisper shares the one MLX thread with generation; mlx 0.32 fails an array used off its thread."""
        import threading
        import tts

        audio = Path(temp_data_dir) / "clip.wav"
        audio.write_bytes(b"RIFF")
        seen = []
        monkeypatch.setattr(tts, "transcribe", lambda path, **kw: seen.append(threading.current_thread().name) or {"text": "Hi.", "duration": 1.0})
        assert client.post("/transcribe-path", json={"audio_path": str(audio)}).status_code == 200
        assert seen and seen[0].startswith("mlx"), seen


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
        assert "tts" in data["models"]
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
            assert "license" in m
        licences = {m["model_name"]: m["license"] for m in models}
        assert licences["qwen-tts-1.7B"] == "apache-2.0"


# ---------------------------------------------------------------------------
# MODEL_REGISTRY
# ---------------------------------------------------------------------------


class TestModelRegistry:
    def test_registry_contains_expected_models(self):
        expected = {
            "whisper-medium",
            "whisper-large-v3-turbo",
            "qwen-tts-1.7B",
            "cosyvoice3-0.5B",
        }
        assert set(MODEL_REGISTRY.keys()) == expected

    def test_tts_rows_declare_transcript_use_and_licence(self):
        for model_name, entry in MODEL_REGISTRY.items():
            if entry["category"] == "tts":
                assert isinstance(entry["ref_text"], bool), model_name
                assert isinstance(entry["license"], str) and entry["license"], model_name

    def test_each_entry_has_required_fields(self):
        required_fields = {"repo_id", "display_name", "category", "recommended"}
        for model_name, entry in MODEL_REGISTRY.items():
            for field in required_fields:
                assert field in entry, f"Model '{model_name}' missing field '{field}'"

    def test_categories_are_valid_values(self):
        valid_categories = {"transcription", "tts", "voice-conversion"}
        for model_name, entry in MODEL_REGISTRY.items():
            assert entry["category"] in valid_categories, (
                f"Model '{model_name}' has invalid category '{entry['category']}'"
            )

    def test_recommended_field_is_boolean(self):
        for model_name, entry in MODEL_REGISTRY.items():
            assert isinstance(entry["recommended"], bool), (
                f"Model '{model_name}' recommended field is not boolean"
            )

    def test_repo_id_is_nonempty_string(self):
        for model_name, entry in MODEL_REGISTRY.items():
            assert isinstance(entry["repo_id"], str) and len(entry["repo_id"]) > 0, (
                f"Model '{model_name}' has empty or non-string repo_id"
            )


# ---------------------------------------------------------------------------
# _LEGACY_MODEL_ALIASES
# ---------------------------------------------------------------------------


class TestLegacyModelAliases:
    def test_all_aliases_map_to_valid_registry_keys(self):
        for alias, canonical in _LEGACY_MODEL_ALIASES.items():
            assert canonical in MODEL_REGISTRY, (
                f"Legacy alias '{alias}' maps to '{canonical}' which is not in MODEL_REGISTRY"
            )

    def test_whisper_alias_maps_to_turbo(self):
        assert _LEGACY_MODEL_ALIASES["whisper"] == "whisper-large-v3-turbo"

    def test_qwen_alias_maps_to_canonical(self):
        assert _LEGACY_MODEL_ALIASES["qwen"] == "qwen-tts-1.7B"

    def test_cosyvoice3_alias_maps_to_canonical(self):
        assert _LEGACY_MODEL_ALIASES["cosyvoice3"] == "cosyvoice3-0.5B"

    def test_case_insensitive_aliases_exist(self):
        """Lowercase aliases for case-sensitive model names should exist."""
        assert "qwen-tts-1.7b" in _LEGACY_MODEL_ALIASES
        assert "cosyvoice3-0.5b" in _LEGACY_MODEL_ALIASES


# ---------------------------------------------------------------------------
# Generation progress and cancel
# ---------------------------------------------------------------------------


def _fake_voice_convert(chunk_delay: float, converted: list):
    """Stand-in for _do_voice_convert that runs the real chunker over 100s of silence, without a model."""
    import asyncio
    import time as _time

    import numpy as np

    from chunked_tts import convert_in_overlapping_chunks

    async def fake(*, set_status, set_progress, should_cancel, original_duration, **_):
        set_status("generating")

        def convert(chunk):
            _time.sleep(chunk_delay)
            converted.append(len(chunk))
            return chunk

        sr = 16000
        audio = await asyncio.to_thread(
            convert_in_overlapping_chunks,
            np.zeros(int(100 * sr), dtype=np.float32),
            sr,
            convert,
            on_progress=set_progress,
            should_cancel=should_cancel,
        )
        return audio, sr, "Voice conversion"

    return fake


def _submit_convert(client, temp_data_dir):
    """Queue a voice conversion for a stub source file and return its generation id."""
    source = Path(temp_data_dir) / "source.wav"
    source.write_bytes(b"RIFF")
    response = client.post("/voice-convert", json={
        "profile_id": "p1",
        "source_audio_path": str(source),
        "original_duration": 100.0,
    })
    assert response.status_code == 200, response.text
    return response.json()["id"]


def _wait_for(client, gen_id, predicate, timeout=20.0):
    """Poll a generation's status until predicate(status_json) holds."""
    import time as _time

    deadline = _time.time() + timeout
    while _time.time() < deadline:
        data = client.get(f"/generate/{gen_id}/status").json()
        if predicate(data):
            return data
        _time.sleep(0.05)
    raise AssertionError(f"generation {gen_id} never reached the expected state: {data}")


class TestGenerationProgressAndCancel:
    def test_status_reports_chunk_progress_to_completion(self, client, temp_data_dir, monkeypatch):
        import server

        converted = []
        monkeypatch.setattr(server, "_do_voice_convert", _fake_voice_convert(0.01, converted))
        gen_id = _submit_convert(client, temp_data_dir)
        data = _wait_for(client, gen_id, lambda d: d["status"] in ("completed", "error"))
        assert data["status"] == "completed", data
        assert data["progress"]["total"] == len(converted) > 1
        assert data["progress"]["done"] == data["progress"]["total"]

    def test_the_runner_hands_each_job_the_callbacks_into_its_own_record(self, temp_data_dir, monkeypatch):
        """Both routes queue _run_generation, which gives the job its status, progress and cancel callbacks,
        so the speech and conversion routes cannot report a job differently."""
        import asyncio

        import numpy as np

        import server

        monkeypatch.setattr(server, "DATA_DIR", Path(temp_data_dir))
        gen_id = server._new_generation()
        seen = []

        async def job(*, set_status, set_progress, should_cancel):
            set_status("generating")
            set_progress(1, 2)
            seen.append((server._generations[gen_id]["status"], should_cancel()))
            return np.zeros(160, dtype=np.float32), 16000, "Test job"

        asyncio.run(server._run_generation(gen_id, job))
        record = server._generations.pop(gen_id)
        assert seen == [("generating", False)], record
        assert record["status"] == "completed"
        assert record["progress"] == {"done": 1, "total": 2}

    def test_cancel_stops_a_running_conversion_between_chunks(self, client, temp_data_dir, monkeypatch):
        import server

        converted = []
        monkeypatch.setattr(server, "_do_voice_convert", _fake_voice_convert(0.2, converted))
        gen_id = _submit_convert(client, temp_data_dir)
        _wait_for(client, gen_id, lambda d: d["progress"]["done"] >= 1)
        assert client.post(f"/generate/{gen_id}/cancel").status_code == 200
        data = _wait_for(client, gen_id, lambda d: d["status"] in ("cancelled", "completed", "error"))
        assert data["status"] == "cancelled"
        assert len(converted) < data["progress"]["total"]

    def test_cancel_during_the_last_chunk_is_not_saved_as_completed(self, client, temp_data_dir, monkeypatch):
        """A short recording is one chunk: a cancel that lands while it runs must still end cancelled."""
        import asyncio

        import numpy as np

        import server

        async def one_chunk(*, set_status, set_progress, should_cancel, **_):
            set_status("generating")
            set_progress(0, 1)
            while not should_cancel():  # the model is still running when the cancel arrives
                await asyncio.sleep(0.01)
            set_progress(1, 1)
            return np.zeros(16000, dtype=np.float32), 16000, "Voice conversion"

        monkeypatch.setattr(server, "_do_voice_convert", one_chunk)
        gen_id = _submit_convert(client, temp_data_dir)
        _wait_for(client, gen_id, lambda d: d["status"] == "generating")
        assert client.post(f"/generate/{gen_id}/cancel").status_code == 200
        data = _wait_for(client, gen_id, lambda d: d["status"] in ("cancelled", "completed", "error"))
        assert data["status"] == "cancelled"
        assert not (Path(temp_data_dir) / "generations" / f"{gen_id}.wav").exists()

    def test_cancel_drops_a_queued_conversion_before_it_runs(self, client, temp_data_dir, monkeypatch):
        import server

        converted = []
        monkeypatch.setattr(server, "_do_voice_convert", _fake_voice_convert(0.2, converted))
        first = _submit_convert(client, temp_data_dir)
        second = _submit_convert(client, temp_data_dir)
        _wait_for(client, first, lambda d: d["progress"]["done"] >= 1)
        client.post(f"/generate/{second}/cancel")
        assert client.get(f"/generate/{second}/status").json()["status"] == "cancelled"
        client.post(f"/generate/{first}/cancel")
        _wait_for(client, first, lambda d: d["status"] == "cancelled")
        assert client.get(f"/generate/{second}/status").json()["progress"]["done"] == 0

    def test_worker_survives_a_queued_job_whose_record_aged_out(self, client, temp_data_dir, monkeypatch):
        import server

        converted = []
        monkeypatch.setattr(server, "_do_voice_convert", _fake_voice_convert(0.2, converted))
        first = _submit_convert(client, temp_data_dir)
        second = _submit_convert(client, temp_data_dir)
        _wait_for(client, first, lambda d: d["progress"]["done"] >= 1)
        client.post(f"/generate/{second}/cancel")
        del server._generations[second]  # what the hourly cleanup does to a long-waiting cancelled job
        client.post(f"/generate/{first}/cancel")
        _wait_for(client, first, lambda d: d["status"] == "cancelled")
        third = _submit_convert(client, temp_data_dir)
        _wait_for(client, third, lambda d: d["status"] == "completed")

    def test_cancel_unknown_generation_is_404(self, client):
        assert client.post("/generate/does-not-exist/cancel").status_code == 404


# ---------------------------------------------------------------------------
# Repos an engine fetches by itself (``extra_repos``)
# ---------------------------------------------------------------------------


def _cache_repo(models_dir: Path, repo_id: str) -> Path:
    """Write ``repo_id`` the way huggingface_hub lays out a downloaded snapshot (blobs, snapshot, ref)."""
    import hashlib

    root = models_dir / f"models--{repo_id.replace('/', '--')}"
    commit = hashlib.sha1(repo_id.encode()).hexdigest()  # commit hashes are per repo, never shared
    blob = hashlib.sha256(repo_id.encode()).hexdigest()
    (root / "blobs").mkdir(parents=True)
    (root / "blobs" / blob).write_bytes(b"weights")
    (root / "snapshots" / commit).mkdir(parents=True)
    (root / "snapshots" / commit / "model.safetensors").symlink_to(f"../../blobs/{blob}")
    (root / "refs").mkdir()
    (root / "refs" / "main").write_text(commit)
    return root


class TestEngineExtraRepos:
    """An engine that fetches a second repo (CosyVoice's 1 GB S3 tokenizer) must not look downloaded without it."""

    @pytest.fixture(autouse=True)
    def _fresh_cache(self, monkeypatch):
        import server

        monkeypatch.setattr(server, "_model_cache", {})

    def _status(self, client, name):
        return next(m for m in client.get("/models/status").json()["models"] if m["model_name"] == name)

    def test_rows_name_the_repos_their_engines_fetch(self):
        """Found by generating each engine with HF_HUB_OFFLINE=1 and only the row's own repo present."""
        assert MODEL_REGISTRY["cosyvoice3-0.5B"]["extra_repos"] == ["mlx-community/S3TokenizerV3"]

    def test_status_is_not_downloaded_until_the_extra_repo_is(self, client, temp_data_dir):
        models = Path(temp_data_dir) / "models"
        _cache_repo(models, MODEL_REGISTRY["cosyvoice3-0.5B"]["repo_id"])
        assert self._status(client, "cosyvoice3-0.5B")["downloaded"] is False
        _cache_repo(models, "mlx-community/S3TokenizerV3")
        assert self._status(client, "cosyvoice3-0.5B")["downloaded"] is True

    def test_health_needs_the_voice_conversion_tokenizer(self, client, temp_data_dir):
        _cache_repo(Path(temp_data_dir) / "models", MODEL_REGISTRY["cosyvoice3-0.5B"]["repo_id"])
        assert client.get("/health").json()["models"]["cosyvoice"] is False

    def test_download_fetches_the_extra_repo_too(self, client, monkeypatch):
        import huggingface_hub

        fetched = []
        monkeypatch.setattr(huggingface_hub, "snapshot_download", lambda repo, cache_dir: fetched.append(repo) or cache_dir)
        body = client.post("/models/download", json={"model_name": "cosyvoice3-0.5B"}).text
        assert fetched == ["mlx-community/Fun-CosyVoice3-0.5B-2512-8bit", "mlx-community/S3TokenizerV3"]
        assert "Download complete" in body

    def test_delete_removes_the_extra_repo(self, client, temp_data_dir):
        models = Path(temp_data_dir) / "models"
        main = _cache_repo(models, MODEL_REGISTRY["cosyvoice3-0.5B"]["repo_id"])
        extra = _cache_repo(models, "mlx-community/S3TokenizerV3")
        assert client.delete("/models/cosyvoice3-0.5B").status_code == 200
        assert not main.exists() and not extra.exists()

    def test_delete_keeps_an_extra_repo_another_row_needs(self, client, temp_data_dir, monkeypatch):
        import server

        registry = {name: dict(entry) for name, entry in MODEL_REGISTRY.items()}
        registry["qwen-tts-1.7B"]["extra_repos"] = ["mlx-community/S3TokenizerV3"]
        monkeypatch.setattr(server, "MODEL_REGISTRY", registry)
        models = Path(temp_data_dir) / "models"
        _cache_repo(models, registry["cosyvoice3-0.5B"]["repo_id"])
        shared = _cache_repo(models, "mlx-community/S3TokenizerV3")
        assert client.delete("/models/cosyvoice3-0.5B").status_code == 200
        assert shared.exists()

    def test_delete_of_a_partial_download_removes_what_is_there(self, client, temp_data_dir):
        extra = _cache_repo(Path(temp_data_dir) / "models", "mlx-community/S3TokenizerV3")
        assert client.delete("/models/cosyvoice3-0.5B").status_code == 200
        assert not extra.exists()


def test_cosyvoice_loader_loads_network_and_tokenizers_before_returning(tmp_path, monkeypatch):
    """The vendored Model loads lazily on the first generate; the server's load step must do that work."""
    from cosyvoice_mlx import loader
    from cosyvoice_mlx.tts.models import cosyvoice3

    loaded = []
    monkeypatch.setattr(loader, "get_model_path", lambda repo: tmp_path)
    monkeypatch.setattr(loader, "load_config", lambda path: {"model_type": "cosyvoice3"})
    monkeypatch.setattr(cosyvoice3.Model, "_ensure_model_loaded", lambda self: loaded.append("network"))
    monkeypatch.setattr(cosyvoice3.Model, "_ensure_tokenizers_loaded", lambda self: loaded.append("tokenizers"))
    model = loader.load_cosyvoice3("mlx-community/Fun-CosyVoice3-0.5B-2512-8bit")
    assert loaded == ["network", "tokenizers"]
    assert model.config.model_path == str(tmp_path)
