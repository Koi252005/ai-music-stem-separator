"""app/routes/jobs.py — REST API endpoints for the stem-separation job system.

Endpoints
---------
POST   /api/jobs                         Upload file, create and queue a job.
GET    /api/jobs/{job_id}                Poll job status.
GET    /api/jobs/{job_id}/stems/{stem}   Stream one stem WAV file.
GET    /api/jobs/{job_id}/download       Download ZIP of all stems.
DELETE /api/jobs/{job_id}                Cancel / delete a job and its files.
GET    /api/models                       List available separation models.
"""
from __future__ import annotations

import logging
import shutil
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse

from app.config import (
    MAX_UPLOAD_BYTES,
    SUPPORTED_EXTENSIONS,
    UPLOADS_DIR,
)
from app.services.job_service import JobStatus, job_service
from app.utils import sanitize_filename

router = APIRouter(prefix="/api")
log = logging.getLogger(__name__)

# ── Model catalogue ───────────────────────────────────────────────────────────

MODELS = [
    {
        "id": "guitar",
        "name": "Electric Guitar (MelBand-Roformer)",
        "description": "Dedicated electric guitar isolation. Produces: electric_guitar, no_electric_guitar.",
        "stems": ["electric_guitar", "no_electric_guitar"],
        "note": "Specialist model — cleaner guitar separation than general-purpose models.",
    },
    {
        "id": "htdemucs_ft",
        "name": "Stem Basic (htdemucs_ft)",
        "description": "4-stem separation: vocals, drums, bass, other.",
        "stems": ["vocals", "drums", "bass", "other"],
        "note": "'other' contains keys, synths, and everything not explicitly separated. Percussion is included in 'drums', not isolated separately.",
    },
    {
        "id": "htdemucs_6s",
        "name": "Stem Extended (htdemucs_6s)",
        "description": "6-stem separation: vocals, drums, bass, guitar, piano, other.",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other"],
        "note": "Includes guitar and piano stems. 'other' = remaining elements.",
    },
    {
        "id": "vocal_hq",
        "name": "Vocal Quality (htdemucs_ft)",
        "description": "Uses htdemucs_ft optimised for vocal extraction.",
        "stems": ["vocals", "drums", "bass", "other"],
        "note": "Same model as Stem Basic; select this when vocal quality is the priority.",
    },
]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/models")
async def list_models():
    return {"models": MODELS}


@router.post("/jobs")
async def create_job(
    file: UploadFile = File(...),
    model_id: str = Form("htdemucs_ft"),
    device: str = Form("auto"),
):
    """Accept an uploaded audio file and start a separation job."""

    # Validate extension
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '{suffix}'. "
                   f"Supported: {sorted(SUPPORTED_EXTENSIONS)}",
        )

    # Validate model
    valid_model_ids = {m["id"] for m in MODELS}
    if model_id not in valid_model_ids:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown model '{model_id}'. Available: {sorted(valid_model_ids)}",
        )

    # Validate device
    if device not in ("auto", "cpu", "cuda"):
        raise HTTPException(status_code=400, detail="device must be auto, cpu, or cuda")

    # ── Save file first, THEN create job ─────────────────────────────────────
    # Critical: worker starts as soon as job is created; file must exist first.
    import uuid as _uuid
    job_id = str(_uuid.uuid4())
    safe_name = sanitize_filename(Path(file.filename or "audio").stem)
    upload_dir = UPLOADS_DIR / job_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / f"input{suffix}"

    try:
        total = 0
        with dest.open("wb") as f_out:
            while chunk := await file.read(1 << 20):  # 1 MB chunks
                total += len(chunk)
                if total > MAX_UPLOAD_BYTES:
                    dest.unlink(missing_ok=True)
                    shutil.rmtree(upload_dir, ignore_errors=True)
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large (max {MAX_UPLOAD_BYTES // 1_048_576} MB).",
                    )
                f_out.write(chunk)
    except HTTPException:
        raise
    except Exception as exc:
        shutil.rmtree(upload_dir, ignore_errors=True)
        log.exception("Failed to save upload for job %s", job_id)
        raise HTTPException(status_code=500, detail=str(exc))

    log.info("Saved %d bytes as %s for job %s", total, dest.name, job_id)

    # Now create job (worker can safely start — file is on disk)
    job = job_service.create_job(
        model_id=model_id,
        device=device,
        input_filename=safe_name,
        job_id=job_id,
    )
    return _job_response(job)



@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_response(job)


@router.get("/jobs/{job_id}/stems/{stem_name}")
async def get_stem(job_id: str, stem_name: str):
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Job not completed (status={job.status})")

    stem_path = job.stem_paths.get(stem_name)
    if stem_path is None or not stem_path.exists():
        raise HTTPException(status_code=404, detail=f"Stem '{stem_name}' not found")

    return FileResponse(
        str(stem_path),
        media_type="audio/wav",
        filename=stem_path.name,
    )


@router.get("/jobs/{job_id}/download")
async def download_zip(job_id: str):
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Job not completed")
    if job.zip_path is None or not job.zip_path.exists():
        raise HTTPException(status_code=404, detail="ZIP file not found")

    return FileResponse(
        str(job.zip_path),
        media_type="application/zip",
        filename=f"{job.input_filename}_stems.zip",
    )


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    deleted = job_service.delete_job(job_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"deleted": True, "job_id": job_id}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _job_response(job) -> dict:
    elapsed = None
    if job.started_at and job.finished_at:
        elapsed = round(job.finished_at - job.started_at, 1)
    elif job.started_at:
        import time
        elapsed = round(time.time() - job.started_at, 1)

    return {
        "id": job.id,
        "status": job.status,
        "model_id": job.model_id,
        "device": job.device,
        "stage_detail": job.stage_detail,
        "error": job.error,
        "stems": job.stems,
        "input_filename": job.input_filename,
        "elapsed_seconds": elapsed,
        "download_url": (
            f"/api/jobs/{job.id}/download"
            if job.status == JobStatus.COMPLETED
            else None
        ),
    }
