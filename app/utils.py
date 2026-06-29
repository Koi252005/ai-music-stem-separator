"""app/utils.py — File-handling utilities for Windows-safe paths."""
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# Characters forbidden in Windows file/directory names.
_WIN_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Trailing dots/spaces are also forbidden on Windows.
_WIN_TRAILING = re.compile(r'[. ]+$')


def sanitize_filename(name: str, max_len: int = 100) -> str:
    """Return a Windows-safe filename derived from *name*.

    - Normalises Unicode to NFC (preserves Vietnamese characters).
    - Strips characters forbidden in Windows paths.
    - Collapses runs of spaces/underscores to a single underscore.
    - Truncates to *max_len* characters.
    - Falls back to ``"file"`` if the result is empty.
    """
    # NFC normalisation keeps Vietnamese diacritics intact.
    name = unicodedata.normalize("NFC", name)
    name = _WIN_FORBIDDEN.sub("_", name)
    name = _WIN_TRAILING.sub("", name)
    name = re.sub(r"[\s_]+", "_", name).strip("_")
    name = name[:max_len]
    return name or "file"


def safe_stem(path: Path) -> str:
    """Return a sanitized version of *path.stem* (filename without extension)."""
    return sanitize_filename(path.stem)
