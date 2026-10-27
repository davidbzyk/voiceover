"""Tests for the text-to-speech engine path: one generic mlx-audio path for every TTS row."""

import asyncio
import math
import threading
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

    async def fake_load(engine, repo_id):
        recorded.append(("load", engine, repo_id))

    async def fake_speak(text, ref_audio, ref_text, seed=None, **limits):
        recorded.append(("speak", text, ref_audio, ref_text, seed, limits))
        return np.zeros(SR // 10, dtype=np.float32), SR

    monkeypatch.setattr(tts, "load_tts_engine", fake_load)
    monkeypatch.setattr(tts, "load_reference", lambda path: ("decoded", path))
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
    assert speaks[0][2] == ("decoded", SAMPLES[-1]["audio_path"])  # the last sample is the reference


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
    with pytest.raises(ConversionCancelled):
        run_generate("qwen-tts-1.7B", segments=segments, should_cancel=lambda: any(c[0] == "speak" for c in calls))
    assert len([c for c in calls if c[0] == "speak"]) == 1


def test_cancel_stops_between_the_sub_chunks_of_a_long_segment(calls):
    """A segment over the 800-character limit is spoken in sub-chunks; a cancel during one stops the rest."""
    sentence = "This sentence is here to make one long segment for the sub-chunk path. " * 6
    segments = [{"text": sentence * 3, "start": 0.0, "end": 60.0}]
    with pytest.raises(ConversionCancelled):
        run_generate("qwen-tts-1.7B", segments=segments, should_cancel=lambda: any(c[0] == "speak" for c in calls))
    assert len([c for c in calls if c[0] == "speak"]) == 1


def test_the_voice_sample_is_decoded_once_per_generation(monkeypatch):
    """Every segment is spoken from the same reference; decoding it per segment repeats file I/O and resampling."""
    decoded = []
    monkeypatch.setattr(tts, "_tts_model", _FakeModel())
    monkeypatch.setattr(tts, "load_tts_engine", lambda engine, repo_id: asyncio.sleep(0))
    monkeypatch.setattr(profiles, "get_samples", lambda data_dir, pid: SAMPLES)
    monkeypatch.setattr("mlx_audio.utils.load_audio", lambda path, sample_rate: decoded.append(path) or np.zeros(10))
    segments = [{"text": f"Line {i}.", "start": float(i), "end": i + 0.5} for i in range(3)]
    run_generate("qwen-tts-1.7B", segments=segments)
    assert decoded == [SAMPLES[-1]["audio_path"]]


def _budget_tokens(engine, expected_s):
    """The max_tokens a phrase expected to last ``expected_s`` gets from ``engine``."""
    tps = server.MODEL_REGISTRY[engine]["tokens_per_second"]
    return math.ceil(tps * (server.SPEECH_BUDGET_RATIO * expected_s + server.SPEECH_BUDGET_PAD_S))


def test_each_phrase_is_bounded_by_its_own_length(calls):
    """MOSS spoke "My fellow Americans," (1.02 s) for 48 s and on, nearly exhausting a 137 GB Mac;
    every phrase now gets a token budget from its own length."""
    segments = [
        {"text": "My fellow Americans,", "start": 0.0, "end": 1.02},
        {"text": "I'm speaking to you tonight from the Oval Office.", "start": 1.2, "end": 4.18},
    ]
    run_generate("qwen-tts-1.7B", segments=segments)
    budgets = [c[5]["max_tokens"] for c in calls if c[0] == "speak"]
    assert budgets == [_budget_tokens("qwen-tts-1.7B", 1.02), _budget_tokens("qwen-tts-1.7B", 2.98)]


def test_moss_is_told_each_phrases_spoken_length(calls):
    """Told nothing, MOSS ran to its bound on 2-3 of 8 seeds; told the length, it stopped there 16 of 16.
    The target leaves out the pauses the padder puts back, so the phrase still fits its slot."""
    words = [
        {"word": " My", "start": 0.0, "end": 0.2},
        {"word": " fellow", "start": 0.4, "end": 0.7},  # 0.2 s pause before
        {"word": " Americans,", "start": 0.7, "end": 1.02},
    ]
    run_generate("moss-tts-local-v1.5", segments=[{"text": "My fellow Americans,", "start": 0.0, "end": 1.02, "words": words}])
    speak = next(c for c in calls if c[0] == "speak")
    assert speak[5]["tokens"] == math.ceil((1.02 - 0.2) * 12.5)
    assert speak[5]["max_tokens"] == _budget_tokens("moss-tts-local-v1.5", 1.02 - 0.2)


def test_moss_is_never_told_less_than_the_target_it_follows(calls):
    """Whisper timed "you know," at 0.3 s; told 4 tokens MOSS ran to its bound on 6 of 6 seeds and failed
    the 410 s recording. It never ran on with a target of 10 tokens or more (52 of 52 runs, four phrases)."""
    run_generate("moss-tts-local-v1.5", segments=[{"text": "you know,", "start": 0.0, "end": 0.3}])
    speak = next(c for c in calls if c[0] == "speak")
    assert speak[5]["tokens"] == server.MODEL_REGISTRY["moss-tts-local-v1.5"]["length_hint"]["min"] == 10


def test_text_without_timing_is_bounded_by_its_length(calls):
    run_generate("fish-s2-pro")  # "Thanks for watching.", the Create Voice shape: no segments
    expected_s = len("Thanks for watching.") / server.SPEECH_CHARS_PER_S
    assert [c[5] for c in calls if c[0] == "speak"] == [{"max_tokens": _budget_tokens("fish-s2-pro", expected_s)}]


def test_an_engine_that_sets_its_own_length_gets_no_budget(calls):
    """OmniVoice is not autoregressive: its length comes from the text, so it cannot run on."""
    run_generate("omnivoice")
    assert [c[5] for c in calls if c[0] == "speak"] == [{}]


def _runaway_speaker(monkeypatch, runaways):
    """Make the engine run to its bound on the first ``runaways`` attempts, then stop normally."""
    attempts = []

    async def speak(text, ref_audio, ref_text, seed=None, **limits):
        attempts.append((seed, limits["max_tokens"]))
        tps = server.MODEL_REGISTRY["moss-tts-local-v1.5"]["tokens_per_second"]
        seconds = limits["max_tokens"] / tps if len(attempts) <= runaways else 1.0
        return np.zeros(int(seconds * SR), dtype=np.float32), SR

    monkeypatch.setattr(tts, "generate_speech", speak)
    return attempts


def test_a_phrase_that_runs_to_its_bound_is_spoken_again_with_a_new_seed(calls, monkeypatch):
    attempts = _runaway_speaker(monkeypatch, runaways=1)
    segments = [{"text": "My fellow Americans,", "start": 0.0, "end": 1.02}]
    statuses = []
    audio, sr, _ = asyncio.run(
        server._do_generate(
            set_status=statuses.append, data_dir=Path("/data"), engine="moss-tts-local-v1.5", profile_id="p",
            text="My fellow Americans,", segments=segments, original_duration=2.0,
        )
    )
    assert len(attempts) == 2 and attempts[0][0] != attempts[1][0], attempts
    assert "retrying" in statuses  # a status change, so the app does not read the retry as a stall
    assert len(audio) == 2 * sr  # the phrase is placed in the 2 s recording


def test_a_phrase_that_never_stops_fails_the_job_naming_the_engine(calls, monkeypatch):
    attempts = _runaway_speaker(monkeypatch, runaways=99)
    segments = [{"text": "My fellow Americans,", "start": 0.0, "end": 1.02}]
    with pytest.raises(ValueError, match="MOSS-TTS Local v1.5 kept speaking past"):
        run_generate("moss-tts-local-v1.5", segments=segments)
    assert len(attempts) == server.SPEECH_ATTEMPTS


def test_a_runaway_phrase_keeps_its_words_out_of_the_log_and_the_error(calls, monkeypatch, caplog):
    # The sidecar logs transcripts by length only; the error reaches the app's log too.
    _runaway_speaker(monkeypatch, runaways=99)
    segments = [{"text": "My fellow Americans,", "start": 0.0, "end": 1.02}]
    with caplog.at_level("INFO"), pytest.raises(ValueError) as failure:
        run_generate("moss-tts-local-v1.5", segments=segments)
    assert "fellow" not in str(failure.value)
    assert "fellow" not in caplog.text


def test_generate_speech_passes_the_budget_to_the_model(monkeypatch):
    model = _FakeModel()
    monkeypatch.setattr(tts, "_tts_model", model)
    asyncio.run(tts.generate_speech("Hi.", np.zeros(10), None, max_tokens=63, tokens=13))
    assert model.kwargs["max_tokens"] == 63 and model.kwargs["tokens"] == 13


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


class _ThreadRecordingModel(_FakeModel):
    """A _FakeModel that records the thread each generate call runs on."""

    def __init__(self, seen):
        super().__init__()
        self.seen = seen

    def generate(self, **kwargs):
        self.seen.append(("generate", threading.current_thread().name))
        yield from super().generate(**kwargs)


def test_loading_decoding_and_generating_run_on_the_mlx_thread(monkeypatch):
    """mlx 0.32 fails an array not yet evaluated on any thread but its own; one MLX thread does all of it."""
    seen = []
    monkeypatch.setattr(tts, "_tts_model", None)
    monkeypatch.setattr(tts, "_tts_engine", None)
    monkeypatch.setattr("mlx_audio.tts.utils.load_model", lambda repo: seen.append(("load", threading.current_thread().name)) or _ThreadRecordingModel(seen))
    monkeypatch.setattr("mlx_audio.utils.load_audio", lambda path, sample_rate: seen.append(("reference", threading.current_thread().name)) or np.zeros(10))
    monkeypatch.setattr(profiles, "get_samples", lambda data_dir, pid: SAMPLES)
    run_generate("qwen-tts-1.7B", segments=[{"text": f"Line {i}.", "start": float(i), "end": i + 0.5} for i in range(2)])
    assert [what for what, _ in seen] == ["load", "reference", "generate", "generate"]
    assert all(name.startswith("mlx") for _, name in seen), seen


class _FakeCosyVoice:
    """Stand-in for CosyVoice3: reads the reference first, as the real generate does, and returns the chunk."""

    sample_rate = SR

    def generate(self, *, ref_audio, source_audio, **kwargs):
        np.array(ref_audio)

        class R:
            audio = source_audio

        yield R()


def test_a_voice_sample_over_30_s_converts(monkeypatch, tmp_path):
    """The reference is trimmed to 30 s; on mlx 0.32 a trim made on another thread failed the first chunk
    ("There is no Stream(gpu, 2) in current thread", frozen binary, 60 s sample)."""
    import soundfile as sf
    from cosyvoice_mlx import loader

    sample, source = tmp_path / "sample.wav", tmp_path / "source.wav"
    sf.write(sample, np.zeros(16000 * 40, dtype=np.float32), 16000)
    sf.write(source, np.zeros(16000 * 5, dtype=np.float32), 16000)
    monkeypatch.setattr(server, "_vc_model", None)
    monkeypatch.setattr(server, "_vc_model_name", None)
    monkeypatch.setattr(loader, "load_cosyvoice3", lambda repo: _FakeCosyVoice())
    monkeypatch.setattr(profiles, "get_samples", lambda data_dir, pid: [{"audio_path": str(sample), "reference_text": "Hi."}])
    audio, sr, _ = asyncio.run(server._do_voice_convert(
        set_status=lambda s: None, data_dir=tmp_path, engine="cosyvoice3-0.5B", profile_id="p",
        source_audio_path=str(source), original_duration=5.0,
    ))
    assert sr == SR and len(audio) == 5 * SR


def test_stereo_engine_output_is_downmixed_not_interleaved(monkeypatch):
    """MOSS-TTS Local returns (samples, 2) at 48 kHz (measured: (99840, 2) for a 2.08 s line); flattening
    interleaved the channels into mono twice as long, so the sidecar saved that line as 4.0 s."""

    class _StereoModel(_FakeModel):
        def generate(self, **kwargs):
            class R:
                audio = np.stack([np.full(SR, 0.2, dtype=np.float32), np.full(SR, 0.4, dtype=np.float32)], axis=1)

            yield R()

    monkeypatch.setattr(tts, "_tts_model", _StereoModel())
    audio, sr = asyncio.run(tts.generate_speech("Hi.", np.zeros(10), None))
    assert audio.shape == (SR,) and np.allclose(audio, 0.3)


def test_generate_speech_leaves_sampling_to_the_model(monkeypatch):
    """mlx-audio 0.5.8's generate_audio helper forced temperature 0.7 and MOSS looped to its
    96 s limit; the engine path must pass only text and the voice reference."""
    model = _FakeModel()
    monkeypatch.setattr(tts, "_tts_model", model)
    audio, sr = asyncio.run(tts.generate_speech("Hi.", np.zeros(10), None))
    assert set(model.kwargs) == {"text", "ref_audio", "ref_text"}
    assert sr == SR and len(audio) == SR


def test_loading_another_engine_unloads_the_first(monkeypatch):
    loaded = []
    monkeypatch.setattr("mlx_audio.tts.utils.load_model", lambda repo: loaded.append(repo) or _FakeModel())
    monkeypatch.setattr(tts, "_tts_model", None)
    monkeypatch.setattr(tts, "_tts_engine", None)
    asyncio.run(tts.load_tts_engine("engine-a", "repo/a"))
    asyncio.run(tts.load_tts_engine("engine-a", "repo/a"))
    asyncio.run(tts.load_tts_engine("engine-b", "repo/b"))
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
