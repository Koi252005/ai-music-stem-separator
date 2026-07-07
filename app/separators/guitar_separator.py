"""app/separators/guitar_separator.py — Adapter for the electric-guitar model.

Wraps the original ``roformer_engine`` so the web backend can call it without
breaking ``legacy_cli/remove_guitar.py`` (the legacy CLI). The CLI continues
to work independently.

Output stems
------------
- ``electric_guitar``  — isolated guitar track
- ``no_electric_guitar`` — everything except the guitar (backing track)
"""
from __future__ import annotations

import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from app.config import GUITAR_CONFIG, GUITAR_CKPT, PROJECT_ROOT
from app.separators.base import BaseSeparator

# The roformer_arch/, roformer_engine.py and legacy_cli/ live at project root.
_ROOT = PROJECT_ROOT
for _p in [str(_ROOT), str(_ROOT / "legacy_cli")]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

log = logging.getLogger(__name__)


class GuitarSeparator(BaseSeparator):
    """Electric guitar isolation via MelBand-Roformer Guitar (becruily)."""

    name = "Electric Guitar (MelBand-Roformer)"
    output_stems = ["electric_guitar", "no_electric_guitar"]

    # ── Public API ────────────────────────────────────────────────────────────

    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        device: str = "auto",
        progress_callback=None,
    ) -> dict[str, Path]:
        """Separate electric guitar from the mix.

        Returns paths to ``electric_guitar.wav`` and
        ``no_electric_guitar.wav`` inside *output_dir*.
        """
        _cb = progress_callback or (lambda stage, detail: None)

        if not GUITAR_CONFIG.exists() or not GUITAR_CKPT.exists():
            raise FileNotFoundError(
                f"Guitar model not found.\n"
                f"  config: {GUITAR_CONFIG}\n"
                f"  ckpt:   {GUITAR_CKPT}\n"
                "Run the download commands in models/README.md."
            )

        _cb("loading_model", "Loading MelBand-Roformer Guitar model…")

        import roformer_engine  # type: ignore[import]
        import remove_guitar    # type: ignore[import]  — legacy CLI (decode_to_wav)

        resolved_device = _resolve_device(device)
        _cb("separating", f"Separating guitar on {resolved_device}…")

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError(
                "ffmpeg not found on PATH. Install ffmpeg and retry."
            )

        # Delegate fully to roformer_engine.separate() which manages its own
        # temp directory and calls decode_to_wav internally.
        stems, sr = roformer_engine.separate(
            source_path=input_path,
            ffmpeg=ffmpeg,
            decode_to_wav=remove_guitar.decode_to_wav,
            device=resolved_device,
            config_path=GUITAR_CONFIG,
            ckpt_path=GUITAR_CKPT,
        )

        _cb("postprocessing", "Writing output files…")
        output_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Path] = {}
        stem_map = {
            "electric_guitar": stems["guitar"],
            "no_electric_guitar": stems["no_guitar"],
        }
        for stem_name, tensor in stem_map.items():
            wav = tensor.detach().cpu().numpy()
            peak = float(np.abs(wav).max()) if wav.size else 0.0
            if peak > 1.0:
                wav = wav / peak
            out_path = output_dir / f"{stem_name}.wav"
            sf.write(str(out_path), wav.T, sr, subtype="PCM_16")
            result[stem_name] = out_path

        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_device(device: str) -> str:
    if device == "auto":
        try:
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"
    if device == "cuda":
        try:
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        log.warning("CUDA requested but not available — falling back to CPU.")
        return "cpu"
    return device
