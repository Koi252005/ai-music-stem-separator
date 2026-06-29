"""app/config.py — Centralized configuration.

All paths and environment-tunable settings live here.
Import this module everywhere instead of scattering Path() calls.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── Root paths ────────────────────────────────────────────────────────────────
# Project root = directory that contains this file's parent (app/)
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent

# ── Model paths ───────────────────────────────────────────────────────────────
MODELS_DIR: Path = PROJECT_ROOT / "models"

GUITAR_MODEL_DIR: Path = MODELS_DIR / "mel_band_roformer_guitar"
GUITAR_CONFIG: Path = GUITAR_MODEL_DIR / "config_guitar_becruily.yaml"
GUITAR_CKPT: Path = GUITAR_MODEL_DIR / "becruily_guitar.ckpt"

# ── Job storage ───────────────────────────────────────────────────────────────
UPLOADS_DIR: Path = PROJECT_ROOT / "uploads"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"

# Create on import so we never get FileNotFoundError at runtime.
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Python interpreter for the current environment ────────────────────────────
# Subprocesses (e.g. running Demucs via CLI) must use the same venv.
PYTHON_EXECUTABLE: str = os.environ.get("PYTHON_EXECUTABLE", sys.executable)

# ── Compute device ────────────────────────────────────────────────────────────
DEFAULT_DEVICE: str = os.environ.get("DEFAULT_DEVICE", "auto")  # auto | cpu | cuda

# ── Upload limits ─────────────────────────────────────────────────────────────
MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", "200"))
MAX_UPLOAD_BYTES: int = MAX_UPLOAD_MB * 1_048_576

# ── Supported input formats ───────────────────────────────────────────────────
SUPPORTED_EXTENSIONS: set[str] = {
    ".wav", ".mp3", ".flac", ".m4a", ".aac",
    ".ogg", ".opus", ".wma", ".mp4", ".mkv",
}
