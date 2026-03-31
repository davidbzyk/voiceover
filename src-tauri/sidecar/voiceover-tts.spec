# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VoiceOver TTS sidecar (macOS arm64).

Build:
    pyinstaller voiceover-tts.spec

Reference: voicebox/backend/voicebox-server.spec
"""

import sys
from PyInstaller.utils.hooks import collect_all

block_cipher = None

# Collect all data/binaries for complex packages
mlx_data, mlx_binaries, mlx_hiddenimports = collect_all("mlx")
mlx_audio_data, mlx_audio_binaries, mlx_audio_hiddenimports = collect_all(
    "mlx_audio"
)

a = Analysis(
    ["server.py"],
    pathex=[],
    binaries=mlx_binaries + mlx_audio_binaries,
    datas=mlx_data + mlx_audio_data,
    hiddenimports=[
        # FastAPI + ASGI
        "fastapi",
        "uvicorn",
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "starlette",
        "starlette.routing",
        "starlette.responses",
        "anyio",
        "anyio._backends",
        "anyio._backends._asyncio",
        "multipart",
        "python_multipart",
        # MLX Whisper
        "mlx",
        "mlx.core",
        "mlx_whisper",
        # HuggingFace
        "huggingface_hub",
        "huggingface_hub.utils",
        # Our modules
        "tts",
    ]
    + mlx_hiddenimports
    + mlx_audio_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude NVIDIA/CUDA (Apple Silicon only)
        "torch.cuda",
        "nvidia",
        "nvidia_cublas_cu11",
        "nvidia_cuda_nvrtc_cu11",
        "nvidia_cuda_runtime_cu11",
        "nvidia_cudnn_cu11",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="voiceover-tts",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    target_arch="arm64",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="voiceover-tts",
)
