"""app/separators/demucs_separator.py — Adapter for Facebook Demucs models.

Supported models
----------------
- ``htdemucs_ft``  — fine-tuned 4-stem (vocals, drums, bass, other)
- ``htdemucs_6s``  — 6-stem (vocals, drums, bass, guitar, piano, other)

Notes
-----
- ``other`` in htdemucs contains keys, synths, and anything not in the
  explicit stems.  It is NOT percussion separately from drums.
- ``guitar`` and ``piano`` only exist in htdemucs_6s.
- Percussion is NOT a separate Demucs output — the UI must reflect this.
"""
from __future__ import annotations

import logging
import shutil
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf
import torch

from app.separators.base import BaseSeparator

log = logging.getLogger(__name__)

# Maps model_id → list of stem names the model actually produces.
DEMUCS_STEMS: dict[str, list[str]] = {
    "htdemucs_ft": ["vocals", "drums", "bass", "other"],
    "htdemucs_6s": ["vocals", "drums", "bass", "guitar", "piano", "other"],
}


class DemucsSeparator(BaseSeparator):
    """General stem separation using Demucs pretrained models."""

    def __init__(self, model_id: str = "htdemucs_ft"):
        if model_id not in DEMUCS_STEMS:
            raise ValueError(
                f"Unknown Demucs model '{model_id}'. "
                f"Available: {list(DEMUCS_STEMS)}"
            )
        self.model_id = model_id
        self.name = f"Demucs ({model_id})"
        self.output_stems = list(DEMUCS_STEMS[model_id])

    # ── Public API ────────────────────────────────────────────────────────────

    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        device: str = "auto",
        progress_callback=None,
    ) -> dict[str, Path]:
        _cb = progress_callback or (lambda stage, detail: None)

        resolved_device = _resolve_device(device)
        log.info("Demucs %s on %s: %s", self.model_id, resolved_device, input_path)

        _cb("loading_model", f"Loading Demucs model {self.model_id}…")

        # Pre-decode to WAV so Demucs always gets a clean stereo input.
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg not found on PATH.")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_dir = Path(tmp)
            wav_in = tmp_dir / "input.wav"

            _decode_to_wav(input_path, ffmpeg, wav_in)

            _cb("separating", f"Running {self.model_id} on {resolved_device}…")

            import subprocess
            import sys

            # Use Demucs CLI which is robust and handles memory well
            cmd = [
                sys.executable, "-m", "demucs.separate",
                "-n", self.model_id,
                "-d", resolved_device,
                "--filename", "{stem}.{ext}",
                "-o", str(output_dir),
                str(wav_in)
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode != 0:
                log.error("Demucs failed. stderr:\n%s", proc.stderr)
                raise RuntimeError(f"Demucs processing failed:\n{proc.stderr.strip()}")

            _cb("postprocessing", "Writing stem files…")
            
            # Demucs places files in `output_dir / model_id / stem.wav` by default
            demucs_out_dir = output_dir / self.model_id
            
            result: dict[str, Path] = {}
            for stem_name in self.output_stems:
                expected_file = demucs_out_dir / f"{stem_name}.wav"
                if not expected_file.exists():
                    raise RuntimeError(f"Demucs did not produce expected stem: {stem_name}")
                
                # Move to the root of output_dir to match our expected format
                final_path = output_dir / f"{stem_name}.wav"
                # If they are the same (in case demucs changes behavior), do nothing
                if expected_file.resolve() != final_path.resolve():
                    shutil.move(str(expected_file), str(final_path))
                
                result[stem_name] = final_path
                log.debug("Wrote %s (%d bytes)", final_path, final_path.stat().st_size)

            # Cleanup the model subfolder
            if demucs_out_dir.exists() and demucs_out_dir.resolve() != output_dir.resolve():
                shutil.rmtree(demucs_out_dir, ignore_errors=True)

        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_device(device: str) -> str:
    if device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    return device


def _decode_to_wav(src: Path, ffmpeg: str, dst: Path) -> None:
    """Decode any audio format to 44100 Hz stereo WAV via ffmpeg."""
    import subprocess
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-i", str(src),
        "-vn", "-ac", "2", "-ar", "44100",
        "-c:a", "pcm_s16le", str(dst),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed to decode {src}:\n{proc.stderr.strip()}"
        )


def _load_audio(path: Path, target_sr: int) -> tuple[torch.Tensor, int]:
    """Load audio file as a (2, samples) float32 tensor."""
    import torchaudio
    wav, sr = torchaudio.load(str(path))
    if sr != target_sr:
        wav = torchaudio.functional.resample(wav, sr, target_sr)
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    return wav, target_sr
