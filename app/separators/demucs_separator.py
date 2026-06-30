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
import subprocess
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

            import demucs.pretrained
            import demucs.apply
            import torch

            # Load model and move to CPU initially to save VRAM
            model = demucs.pretrained.get_model(self.model_id)
            model.cpu()
            model.eval()

            # Load audio using torchaudio (which works for loading, just not saving on Windows)
            mix, sr = _load_audio(wav_in, model.samplerate)
            
            # Add batch dimension: (1, channels, length)
            mix = mix.unsqueeze(0)

            _cb("separating", "Processing audio…")
            with torch.no_grad():
                out = demucs.apply.apply_model(
                    model, 
                    mix, 
                    device=resolved_device,
                    shifts=1, 
                    split=True, 
                    overlap=0.25, 
                    progress=False
                )
            
            # Remove batch dimension: (sources, channels, length)
            out = out[0]

            _cb("postprocessing", "Writing stem files…")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            result: dict[str, Path] = {}
            for i, stem_name in enumerate(model.sources):
                if stem_name not in self.output_stems:
                    continue # Skip stems we don't care about (though we care about all)
                
                wav = out[i].cpu().numpy()
                peak = float(np.abs(wav).max()) if wav.size else 0.0
                if peak > 1.0:
                    wav = wav / peak
                
                out_path = output_dir / f"{stem_name}.wav"
                sf.write(str(out_path), wav.T, model.samplerate, subtype="PCM_16")
                result[stem_name] = out_path
                log.debug("Wrote %s (%d bytes)", out_path, out_path.stat().st_size)

        return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_device(device: str) -> str:
    """Resolve device string, safely falling back to CPU."""
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


def _decode_to_wav(src: Path, ffmpeg: str, dst: Path) -> None:
    """Decode any audio format to 44100 Hz stereo WAV via ffmpeg."""
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
    """Load WAV file as a (2, samples) float32 tensor using soundfile.
    
    Uses soundfile instead of torchaudio to avoid the torchcodec/FFmpeg
    DLL dependency on Windows (torchaudio >= 2.11 requires torchcodec).
    """
    # soundfile returns (samples, channels) ndarray
    data, sr = sf.read(str(path), dtype="float32", always_2d=True)
    # Transpose to (channels, samples)
    wav = torch.from_numpy(data.T)
    if sr != target_sr:
        # Simple linear resampling via torch — good enough for audio that
        # was already decoded by ffmpeg to the correct sample rate (44100).
        # For the temp WAV we create with _decode_to_wav, sr == target_sr always.
        ratio = target_sr / sr
        new_length = int(wav.shape[1] * ratio)
        wav = torch.nn.functional.interpolate(
            wav.unsqueeze(0), size=new_length, mode="linear", align_corners=False
        ).squeeze(0)
    if wav.shape[0] == 1:
        wav = wav.repeat(2, 1)
    return wav, target_sr
