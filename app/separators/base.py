"""app/separators/base.py — Abstract base class for all stem separators."""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class BaseSeparator(ABC):
    """Common interface every separator must implement."""

    #: Human-readable name shown in the UI.
    name: str = "Unknown"
    #: List of stem names this separator produces (e.g. ["vocals", "drums"]).
    output_stems: list[str] = []

    @abstractmethod
    def separate(
        self,
        input_path: Path,
        output_dir: Path,
        device: str = "auto",
        progress_callback=None,
    ) -> dict[str, Path]:
        """Run separation.

        Parameters
        ----------
        input_path:
            Absolute path to the input audio file (WAV preferred but any
            ffmpeg-decodable format is acceptable).
        output_dir:
            Directory where output WAV files will be written.
        device:
            ``"auto"`` | ``"cpu"`` | ``"cuda"``.
        progress_callback:
            Optional callable ``(stage: str, detail: str) -> None`` that the
            separator calls to report progress.

        Returns
        -------
        dict mapping stem name → absolute Path of the written WAV file.
        """
