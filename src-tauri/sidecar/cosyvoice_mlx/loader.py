"""Load CosyVoice3 for voice conversion (this file is ours, not vendored)."""

from __future__ import annotations

from mlx_audio.utils import get_model_path, load_config

from .tts.models import cosyvoice3


def load_cosyvoice3(repo_id: str):
    """Fetch ``repo_id`` through the HF cache and return CosyVoice3 with its network and tokenizers loaded.

    The vendored ``Model`` is a lazy wrapper: ``load_weights`` does nothing, and the network and the
    S3 tokenizer (``mlx-community/S3TokenizerV3``) load on the first ``generate``. Loading them here
    keeps that work inside the server's load step instead of the first conversion chunk.
    """
    model_path = get_model_path(repo_id)
    config = load_config(model_path)
    config["model_path"] = str(model_path)
    model = cosyvoice3.Model(cosyvoice3.ModelConfig.from_dict(config))
    model._ensure_model_loaded()
    model._ensure_tokenizers_loaded()
    return model
