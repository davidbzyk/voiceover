# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VoiceOver TTS sidecar (macOS arm64).

Build:
    pyinstaller voiceover-tts.spec

Reference: voicebox/backend/voicebox-server.spec
"""

from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules

block_cipher = None

datas = []
binaries = []
hiddenimports = []

# Copy package metadata (required for safetensors format detection)
datas += copy_metadata('safetensors')
datas += copy_metadata('qwen-tts')
datas += copy_metadata('requests')
datas += copy_metadata('transformers')
datas += copy_metadata('huggingface-hub')
datas += copy_metadata('tokenizers')
datas += copy_metadata('tqdm')

# Collect submodules (ensures all .so native extensions are included)
hiddenimports += collect_submodules('mlx')
hiddenimports += collect_submodules('mlx_whisper')
hiddenimports += collect_submodules('mlx_audio')

# MLX needs its Metal shader library and native .dylib bundled explicitly
tmp_ret = collect_all('mlx')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

tmp_ret = collect_all('mlx_metal')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

# Collect all for complex packages
for pkg in ["qwen_tts", "librosa", "lazy_loader", "mlx_audio"]:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

a = Analysis(
    ["server.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
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
        # MLX
        "mlx",
        "mlx.core",
        "mlx.nn",
        "mlx_whisper",
        "mlx_audio",
        "mlx_audio.stt",
        # Qwen TTS
        "qwen_tts",
        "qwen_tts.core",
        # PyTorch
        "torch",
        "torchaudio",
        # HuggingFace
        "huggingface_hub",
        "huggingface_hub.utils",
        "safetensors",
        "safetensors.torch",
        "tokenizers",
        "transformers",
        # Audio
        "soundfile",
        "numpy",
        "scipy",
        "librosa",
        # yt-dlp
        "yt_dlp",
        # Our modules
        "tts",
        "profiles",
        "chunked_tts",
    ]
    + hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude NVIDIA packages (Apple Silicon only — keep torch.cuda as it's
        # imported by mlx_audio for device detection and handles missing gracefully)
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
    a.binaries,
    a.datas,
    [],
    name="voiceover-tts",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    console=True,
    target_arch="arm64",
)
