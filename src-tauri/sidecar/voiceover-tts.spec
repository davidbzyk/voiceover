# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for VoiceOver TTS sidecar (macOS arm64).

Build:
    pyinstaller voiceover-tts.spec

Reference: voicebox/backend/voicebox-server.spec
"""

from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules

datas = []
binaries = []
hiddenimports = []

# Copy package metadata (required for safetensors format detection)
datas += copy_metadata('safetensors')
datas += copy_metadata('requests')
datas += copy_metadata('transformers')
datas += copy_metadata('huggingface-hub')
datas += copy_metadata('tokenizers')
datas += copy_metadata('tqdm')

# Collect submodules (ensures all .so native extensions are included)
hiddenimports += collect_submodules('mlx')
hiddenimports += collect_submodules('cosyvoice_mlx')
# scipy 1.18 imports its vendored array-api backends by name (importlib), which PyInstaller cannot see;
# without them every mlx-audio model that touches scipy.signal fails to load in the frozen binary.
hiddenimports += collect_submodules('scipy._external')
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

# Collect all for complex packages (librosa needs lazy_loader stubs)
for pkg in ["librosa", "lazy_loader", "mlx_audio"]:
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
        "mlx_audio",
        "mlx_audio.stt",
        # HuggingFace
        "huggingface_hub",
        "huggingface_hub.utils",
        "safetensors",
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
        "cosyvoice_mlx",
    ]
    + hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Every engine runs on MLX; torch must not ride in from an older build venv.
        "torch",
        "torchaudio",
        # Exclude NVIDIA packages (Apple Silicon only)
        "nvidia",
        "nvidia.cublas",
        "nvidia.cuda_cupti",
        "nvidia.cuda_nvrtc",
        "nvidia.cuda_runtime",
        "nvidia.cudnn",
        "nvidia.cufft",
        "nvidia.curand",
        "nvidia.cusolver",
        "nvidia.cusparse",
        "nvidia.nccl",
        "nvidia.nvjitlink",
        "nvidia.nvtx",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

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
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity="Developer ID Application",
    entitlements_file="entitlements.plist",
)
