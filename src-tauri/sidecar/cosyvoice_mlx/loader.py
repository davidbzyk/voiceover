"""Load CosyVoice3 weights with mlx-audio's own loading steps (this file is ours, not vendored)."""

from __future__ import annotations

import mlx.core as mx
from mlx_audio.utils import apply_quantization, get_model_path, load_config, load_weights

from .tts.models import cosyvoice3


def load_cosyvoice3(repo_id: str):
    """Fetch ``repo_id`` through the HF cache and return the CosyVoice3 model.

    Mirrors ``mlx_audio.utils.base_load_model``, which only imports models from mlx-audio itself.
    """
    model_path = get_model_path(repo_id)
    config = load_config(model_path)
    config["model_path"] = str(model_path)
    model = cosyvoice3.Model(cosyvoice3.ModelConfig.from_dict(config))
    weights = model.sanitize(load_weights(model_path))
    apply_quantization(model, config, weights, getattr(model, "model_quant_predicate", None))
    model.load_weights(list(weights.items()), strict=True)
    mx.eval(model.parameters())
    model.eval()
    if hasattr(cosyvoice3.Model, "post_load_hook"):
        model = cosyvoice3.Model.post_load_hook(model, model_path)
    return model
