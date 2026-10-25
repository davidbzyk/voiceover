"""Tests for the text-to-speech engine path: one generic mlx-audio path for every TTS row."""

import asyncio
from pathlib import Path

import numpy as np
import pytest

import profiles
import server
import tts
from chunked_tts import ConversionCancelled

SR = 24000
# Shaped like profiles.get_samples() output: the last sample is the voice reference.
SAMPLES = [
    {"id": "a", "audio_path": "/data/profiles/p/samples/a.wav", "reference_text": "First take."},
    {"id": "b", "audio_path": "/data/profiles/p/samples/b.wav", "reference_text": "God, here we go.\n"},
]


@pytest.fixture
def calls(monkeypatch):
    """Replace model loading and generation with recorders; return the list of generate calls."""
    recorded = []

    async def fake_load(models_dir, engine, repo_id):
        recorded.append(("load", engine, repo_id))

    async def fake_speak(text, ref_audio_path, ref_text, seed=None):
        recorded.append(("speak", text, ref_audio_path, ref_text, seed))
        return np.zeros(SR // 10, dtype=np.float32), SR

    monkeypatch.setattr(tts, "load_tts_engine", fake_load)
    monkeypatch.setattr(tts, "generate_speech", fake_speak)
    monkeypatch.setattr(profiles, "get_samples", lambda data_dir, pid: SAMPLES)
    return recorded


def run_generate(engine, *, segments=(), should_cancel=lambda: False, progress=None):
    return asyncio.run(
        server._do_generate(
            set_status=lambda s: None,
            set_progress=(lambda d, t: progress.append((d, t))) if progress is not None else (lambda d, t: None),
            should_cancel=should_cancel,
            data_dir=Path("/data"),
            engine=engine,
            profile_id="p",
            text="Thanks for watching.",
            segments=list(segments),
            original_duration=2.0 if segments else 0.0,
        )
    )


def test_qwen_clones_without_the_transcript(calls):
    """The T2 leak: Qwen given the sample transcript spoke its words; x-vector mode passes none."""
    run_generate("qwen-tts-1.7B")
    speaks = [c for c in calls if c[0] == "speak"]
    assert speaks and all(c[3] is None for c in speaks)
    assert speaks[0][2] == SAMPLES[-1]["audio_path"]


def test_transcript_engines_get_the_last_samples_text(calls, monkeypatch):
    registry = dict(server.MODEL_REGISTRY)
    registry["transcript-engine"] = {**registry["qwen-tts-1.7B"], "ref_text": True}  # a ref_text row
    monkeypatch.setattr(server, "MODEL_REGISTRY", registry)
    run_generate("transcript-engine")
    speak = next(c for c in calls if c[0] == "speak")
    assert speak[3] == "God, here we go."


def test_engine_row_picks_the_repo_that_loads(calls):
    run_generate("qwen-tts-1.7B")
    assert calls[0] == ("load", "qwen-tts-1.7B", server.MODEL_REGISTRY["qwen-tts-1.7B"]["repo_id"])


def test_cancel_stops_before_the_next_segment(calls):
    segments = [{"text": f"Line {i}.", "start": float(i), "end": i + 0.5} for i in range(3)]
    flags = iter([False, True, True])
    with pytest.raises(ConversionCancelled):
        run_generate("qwen-tts-1.7B", segments=segments, should_cancel=lambda: next(flags))
    assert len([c for c in calls if c[0] == "speak"]) == 1


def test_progress_counts_segments(calls):
    segments = [{"text": f"Line {i}.", "start": float(i), "end": i + 0.5} for i in range(3)]
    progress = []
    run_generate("qwen-tts-1.7B", segments=segments, progress=progress)
    assert progress == [(0, 3), (1, 3), (2, 3), (3, 3)]


class _FakeModel:
    sample_rate = SR

    def __init__(self):
        self.kwargs = None

    def generate(self, **kwargs):
        self.kwargs = kwargs

        class R:
            audio = np.ones(SR, dtype=np.float32)

        yield R()


def test_generate_speech_leaves_sampling_to_the_model(monkeypatch):
    """mlx-audio 0.5.8's generate_audio helper forced temperature 0.7 and MOSS looped to its
    96 s limit; the engine path must pass only text and the voice reference."""
    model = _FakeModel()
    monkeypatch.setattr(tts, "_tts_model", model)
    monkeypatch.setattr("mlx_audio.utils.load_audio", lambda path, sample_rate: np.zeros(10))
    audio, sr = asyncio.run(tts.generate_speech("Hi.", "/ref.wav", None))
    assert set(model.kwargs) == {"text", "ref_audio", "ref_text"}
    assert sr == SR and len(audio) == SR


def test_loading_another_engine_unloads_the_first(monkeypatch):
    loaded = []
    monkeypatch.setattr("mlx_audio.tts.utils.load_model", lambda repo: loaded.append(repo) or _FakeModel())
    monkeypatch.setattr(tts, "_tts_model", None)
    monkeypatch.setattr(tts, "_tts_engine", None)
    asyncio.run(tts.load_tts_engine("/models", "engine-a", "repo/a"))
    asyncio.run(tts.load_tts_engine("/models", "engine-a", "repo/a"))
    asyncio.run(tts.load_tts_engine("/models", "engine-b", "repo/b"))
    assert loaded == ["repo/a", "repo/b"]
    assert tts.get_loaded_tts_engine() == "engine-b"


def test_models_land_in_the_data_dir_not_the_default_hf_cache(tmp_path):
    """The hub reads HF_HUB_CACHE once at import; server.py must set it before anything imports it."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if not k.startswith("HF_")}
    code = (
        "import sys; sys.argv = ['server.py', '--port', '1', '--data-dir', sys.argv[1], '--parent-pid', '1']\n"
        "import server, huggingface_hub.constants as c; print(c.HF_HUB_CACHE)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code, str(tmp_path)],
        cwd=Path(__file__).parent, env=env, capture_output=True, text=True, check=True,
    ).stdout.strip().splitlines()[-1]
    assert out == str(tmp_path / "models")


def test_check_imports_passes_for_every_registry_row():
    assert server.check_imports() == 0


def test_check_imports_fails_when_a_row_module_is_missing(monkeypatch, capsys):
    """The frozen binary once lacked scipy._external and no engine could load; the gate must say so."""
    broken = dict(server.MODEL_REGISTRY)
    broken["qwen-tts-1.7B"] = {**broken["qwen-tts-1.7B"], "module": "mlx_audio.tts.models.not_bundled"}
    monkeypatch.setattr(server, "MODEL_REGISTRY", broken)
    assert server.check_imports() == 1
    assert "FAIL qwen-tts-1.7B" in capsys.readouterr().out


def test_check_imports_fails_when_the_copy_ships_without_its_licences(monkeypatch, tmp_path, capsys):
    """collect_submodules bundles only modules; a build that drops the licence texts must fail."""
    import cosyvoice_mlx

    monkeypatch.setattr(cosyvoice_mlx, "__file__", str(tmp_path / "__init__.py"))
    assert server.check_imports() == 1
    assert "FAIL cosyvoice_mlx licence texts" in capsys.readouterr().out
