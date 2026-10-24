# cosyvoice_mlx

CosyVoice3 for MLX, copied from the `mlx-audio-plus` 0.1.8 wheel (MIT, see LICENSE) so voice
conversion runs on the same mlx-audio as the TTS engines. Changes from the wheel: import paths
only (`mlx_lm.models` to `mlx_audio.lm.models`, `mlx_audio.codec.models.s3gen`/`s3tokenizer` to this
package, `..base` to `mlx_audio.tts.models.base`), conversion scripts removed, and `loader.py` added.
Why: `okf/lineage/evidence/cosyvoice-from-mlx-audio-plus.md`.
