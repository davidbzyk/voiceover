# Lineage: Evidence

Distilled probe summaries and execution traces.

## Documents

* [Qwen3-TTS in-context cloning leaks the reference's last words](./qwen3-tts-icl-reference-leak.md) - Measured leak trials and the upstream issue.
* [Whisper loops on Create Voice clips](./whisper-reference-transcript-loop.md) - Why looping segments are dropped after Whisper's retries.
* [Six TTS engines on mlx-audio 0.5.8, and the helper that broke MOSS](./mlx-audio-058-engine-bench.md) - Bench of the six engines on the 0.5.8 pins, before the 0.6.1 bump.
* [mlx 0.32.4 and mlx-audio 0.6.1: faster engines, one MLX thread](./mlx-0324-mlx-audio-061-bump.md) - The bump's bench, A/B and the thread fix it needed.
* [CosyVoice came from an undeclared fork; the sidecar now carries its code](./cosyvoice-from-mlx-audio-plus.md) - Where Replace Voice's model code lives and why.
* [Models loaded from ~/.cache/huggingface, not the app's models folder](./hf-cache-set-after-import.md) - Why HF_HUB_CACHE is set before imports.
* [A MOSS phrase that never stopped, and MLX's unbounded buffer cache](./tts-runaway-and-mlx-cache.md) - The near out-of-memory run, the phrase bound and the cache cap.
