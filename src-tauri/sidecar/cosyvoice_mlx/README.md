# cosyvoice_mlx

CosyVoice3 for MLX, copied from the `mlx-audio-plus` 0.1.8 wheel (MIT, see LICENSE) so voice
conversion runs on the same mlx-audio as the TTS engines. Changes from the wheel: import paths
only (`mlx_lm.models` to `mlx_audio.lm.models`, `mlx_audio.codec.models.s3gen`/`s3tokenizer` to this
package, `..base` to `mlx_audio.tts.models.base`), conversion scripts removed, and `loader.py` added.
`scripts/check-cosyvoice-copy.sh` diffs this package against the wheel with those edits applied.
`licenses/` holds the texts of the projects this code was ported from (CosyVoice, Chatterbox, Matcha-TTS,
S3Tokenizer), which the wheel left out; they come from the fork's `licenses/` at tag v0.1.8 (`a8e07b4`).
Why: `okf/lineage/evidence/cosyvoice-from-mlx-audio-plus.md`.
