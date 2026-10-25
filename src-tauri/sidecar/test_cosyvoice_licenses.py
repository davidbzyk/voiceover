"""Every upstream project the cosyvoice_mlx copy was ported from ships its licence text with it."""

import re
from pathlib import Path

PACKAGE = Path(__file__).parent / "cosyvoice_mlx"
# The licence text for each upstream named in a "Ported to MLX from" header. A new upstream is a new row.
UPSTREAM_LICENCES = {
    "https://github.com/FunAudioLLM/CosyVoice": "cosyvoice.txt",
    "https://github.com/resemble-ai/chatterbox": "chatterbox.txt",
    "https://github.com/shivammehta25/Matcha-TTS": "matcha.txt",
    "https://github.com/xingchensong/S3Tokenizer": "s3tokenizer.txt",
}


def _headers():
    for path in PACKAGE.rglob("*.py"):
        yield path, path.read_text(encoding="utf-8")[:600]


def test_every_ported_upstream_has_a_licence_row():
    upstreams = {m for _, head in _headers() for m in re.findall(r"Ported to MLX from (\S+)", head)}
    assert upstreams <= UPSTREAM_LICENCES.keys(), f"no licence row for {upstreams - UPSTREAM_LICENCES.keys()}"


def test_every_named_licence_text_is_in_the_package():
    named = {m for _, head in _headers() for m in re.findall(r"License: licenses/(\S+)", head)}
    missing = sorted(f for f in named | set(UPSTREAM_LICENCES.values()) if not (PACKAGE / "licenses" / f).is_file())
    assert not missing, f"licence texts missing from cosyvoice_mlx/licenses: {missing}"
