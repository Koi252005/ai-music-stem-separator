"""tests/test_guitar_cli.py — Smoke tests for the legacy guitar CLI.

Tests that remove_guitar.py (the original CLI) still works correctly
both as a script and through the GuitarSeparator adapter.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _make_test_wav(path: Path, duration_s: float = 3.0, sr: int = 44100) -> None:
    """Write a stereo 440 Hz sine-wave WAV to *path*."""
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    ch1 = 0.25 * np.sin(2 * np.pi * 440 * t)
    ch2 = 0.25 * np.sin(2 * np.pi * 550 * t)
    sf.write(str(path), np.stack([ch1, ch2], axis=1), sr, subtype="PCM_16")


class TestGuitarCLI:
    """Black-box tests for the legacy CLI."""

    @pytest.fixture(autouse=True)
    def tmp(self, tmp_path):
        self.tmp = tmp_path

    def _guitar_model_available(self) -> bool:
        config = PROJECT_ROOT / "models" / "mel_band_roformer_guitar" / "config_guitar_becruily.yaml"
        ckpt   = PROJECT_ROOT / "models" / "mel_band_roformer_guitar" / "becruily_guitar.ckpt"
        return config.exists() and ckpt.exists()

    def test_cli_help(self):
        """--help should exit 0 and print usage."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "remove_guitar.py"), "--help"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0
        assert "guitar" in result.stdout.lower() or "guitar" in result.stderr.lower()

    @pytest.mark.skipif(
        not Path(
            PROJECT_ROOT / "models" / "mel_band_roformer_guitar" / "becruily_guitar.ckpt"
        ).exists(),
        reason="Guitar model checkpoint not downloaded",
    )
    def test_cli_separates_wav(self):
        """CLI should produce an output WAV for a synthetic input."""
        in_wav = self.tmp / "input.wav"
        out_wav = self.tmp / "output.wav"
        _make_test_wav(in_wav)

        result = subprocess.run(
            [
                sys.executable, str(PROJECT_ROOT / "remove_guitar.py"),
                str(in_wav), "--device", "cpu", "-o", str(out_wav), "-f", "wav",
            ],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, (
            f"CLI returned {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_wav.exists(), "Output WAV file was not created"
        data, sr = sf.read(str(out_wav))
        assert data.shape[0] > 0, "Output WAV is empty"

    def test_cli_missing_file_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "remove_guitar.py"), "nonexistent.wav"],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode != 0

    def test_cli_missing_model_exits_nonzero(self):
        """Pointing to a non-existent checkpoint should fail gracefully."""
        in_wav = self.tmp / "input.wav"
        _make_test_wav(in_wav)

        result = subprocess.run(
            [
                sys.executable, str(PROJECT_ROOT / "remove_guitar.py"),
                str(in_wav),
                "--roformer-ckpt", str(self.tmp / "fake.ckpt"),
                "--roformer-config", str(self.tmp / "fake.yaml"),
            ],
            capture_output=True, text=True, cwd=str(PROJECT_ROOT),
        )
        assert result.returncode != 0
        assert "not found" in result.stderr.lower() or "error" in result.stderr.lower()


class TestGuitarAdapter:
    """Tests for the GuitarSeparator adapter in app/separators/."""

    @pytest.fixture(autouse=True)
    def tmp(self, tmp_path):
        self.tmp = tmp_path

    def _guitar_model_available(self) -> bool:
        config = PROJECT_ROOT / "models" / "mel_band_roformer_guitar" / "config_guitar_becruily.yaml"
        ckpt   = PROJECT_ROOT / "models" / "mel_band_roformer_guitar" / "becruily_guitar.ckpt"
        return config.exists() and ckpt.exists()

    def test_adapter_import(self):
        """GuitarSeparator must be importable."""
        from app.separators.guitar_separator import GuitarSeparator
        sep = GuitarSeparator()
        assert "electric_guitar" in sep.output_stems
        assert "no_electric_guitar" in sep.output_stems

    def test_adapter_missing_model_raises(self):
        """Adapter should raise FileNotFoundError when model is absent."""
        from unittest.mock import patch
        from app.separators.guitar_separator import GuitarSeparator

        sep = GuitarSeparator()
        in_wav = self.tmp / "input.wav"
        _make_test_wav(in_wav)

        with patch("app.separators.guitar_separator.GUITAR_CONFIG",
                   self.tmp / "fake_config.yaml"), \
             patch("app.separators.guitar_separator.GUITAR_CKPT",
                   self.tmp / "fake.ckpt"):
            with pytest.raises(FileNotFoundError):
                sep.separate(in_wav, self.tmp / "out", device="cpu")
