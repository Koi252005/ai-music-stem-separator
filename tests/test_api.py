"""tests/test_api.py — Integration tests for the FastAPI job REST API.

Uses TestClient so no real model runs — separators are mocked.
"""
import io
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /api/models ───────────────────────────────────────────────────────────────

def test_models_endpoint():
    resp = client.get("/api/models")
    assert resp.status_code == 200
    data = resp.json()
    assert "models" in data
    model_ids = {m["id"] for m in data["models"]}
    assert "guitar" in model_ids
    assert "htdemucs_ft" in model_ids
    assert "htdemucs_6s" in model_ids


# ── /health ───────────────────────────────────────────────────────────────────

def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── POST /api/jobs ─────────────────────────────────────────────────────────────

def _fake_wav_bytes() -> bytes:
    """Return a minimal valid WAV file (44-byte header, no samples)."""
    import struct
    # Minimal 44-byte WAV header for 16-bit stereo 44100 Hz, 0 samples
    data_size = 0
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, 2, 44100, 44100 * 2 * 2, 4, 16,
        b"data", data_size,
    )
    return header


def test_create_job_unsupported_format():
    resp = client.post(
        "/api/jobs",
        files={"file": ("song.xyz", io.BytesIO(b"fake"), "audio/xyz")},
        data={"model_id": "htdemucs_ft", "device": "cpu"},
    )
    assert resp.status_code == 415


def test_create_job_invalid_model():
    resp = client.post(
        "/api/jobs",
        files={"file": ("song.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
        data={"model_id": "nonexistent_model", "device": "cpu"},
    )
    assert resp.status_code == 400


def test_create_job_invalid_device():
    resp = client.post(
        "/api/jobs",
        files={"file": ("song.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
        data={"model_id": "htdemucs_ft", "device": "tpu"},
    )
    assert resp.status_code == 400


def test_create_job_returns_job_id():
    resp = client.post(
        "/api/jobs",
        files={"file": ("test.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
        data={"model_id": "htdemucs_ft", "device": "cpu"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "id" in body
    assert body["status"] in (
        "queued", "preprocessing", "loading_model", "separating",
        "postprocessing", "mixing", "completed", "failed",
    )


# ── GET /api/jobs/{id} ────────────────────────────────────────────────────────

def test_get_job_not_found():
    resp = client.get(f"/api/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_get_job_round_trip():
    # Create a job then immediately fetch it.
    create_resp = client.post(
        "/api/jobs",
        files={"file": ("song.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
        data={"model_id": "guitar", "device": "cpu"},
    )
    assert create_resp.status_code == 200
    job_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id


# ── DELETE /api/jobs/{id} ─────────────────────────────────────────────────────

def test_delete_nonexistent_job():
    resp = client.delete(f"/api/jobs/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_delete_existing_job():
    create_resp = client.post(
        "/api/jobs",
        files={"file": ("song.wav", io.BytesIO(_fake_wav_bytes()), "audio/wav")},
        data={"model_id": "htdemucs_ft", "device": "cpu"},
    )
    job_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/jobs/{job_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["deleted"] is True


# ── Vietnamese filename safety ────────────────────────────────────────────────

@pytest.mark.parametrize("filename", [
    "Nơi này có anh.wav",
    "Tình yêu của em (Live).mp3",
    "Bài hát số 1 [2024].flac",
    "Song: Day 1.wav",
])
def test_vietnamese_filename_accepted(filename):
    """Vietnamese filenames and special characters must not cause 500 errors."""
    resp = client.post(
        "/api/jobs",
        files={"file": (filename, io.BytesIO(_fake_wav_bytes()), "audio/wav")},
        data={"model_id": "htdemucs_ft", "device": "cpu"},
    )
    # Should be 200 (accepted) or at most 413 (too large), never 500
    assert resp.status_code in (200, 201, 413), (
        f"Unexpected status {resp.status_code} for filename '{filename}': "
        f"{resp.text}"
    )
