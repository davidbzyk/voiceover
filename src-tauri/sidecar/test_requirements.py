"""Engine-admission rule 5: every package the sidecar imports is pinned in requirements.txt."""

import ast
import re
import sys
from importlib.metadata import packages_distributions
from pathlib import Path

SIDECAR = Path(__file__).parent
# Imported only by code the sidecar never runs, so not installed; each needs its reason.
NEVER_RUN = {
    "onnx": "cosyvoice_mlx S3TokenizerV3.from_onnx, a conversion helper; the sidecar loads safetensors",
}


def _shipped_sources():
    """The sidecar's own modules and the cosyvoice_mlx copy; tests are not shipped."""
    yield from (p for p in SIDECAR.glob("*.py") if not p.name.startswith("test_"))
    yield from (SIDECAR / "cosyvoice_mlx").rglob("*.py")


def _imported_top_levels():
    """Top-level names of every absolute import in the shipped sources, lazy imports included."""
    names = set()
    for path in _shipped_sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                names.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


def _normalize(dist: str) -> str:
    return re.sub(r"[-_.]+", "-", dist).lower()


def test_every_imported_package_is_pinned():
    pinned = {
        _normalize(line.split("==")[0])
        for line in (SIDECAR / "requirements.txt").read_text().splitlines()
        if "==" in line and not line.lstrip().startswith("#")
    }
    local = {p.stem for p in SIDECAR.glob("*.py")} | {"cosyvoice_mlx"}
    owners = packages_distributions()
    unpinned = {}
    for name in sorted(_imported_top_levels() - local - set(sys.stdlib_module_names) - NEVER_RUN.keys()):
        dists = {_normalize(d) for d in owners.get(name, [name])}
        if not dists & pinned:
            unpinned[name] = sorted(dists)
    assert not unpinned, f"imported but not pinned in requirements.txt: {unpinned}"
