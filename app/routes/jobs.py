"""app/routes/jobs.py — REST API endpoints for the stem-separation job system.

Endpoints
---------
POST   /api/jobs                         Upload file, create and queue a job.
GET    /api/jobs/{job_id}                Poll job status (JSON).
GET    /api/jobs/{job_id}/events         Server-Sent Events stream for job status.
GET    /api/jobs/{job_id}/stems/{stem}   Stream one stem WAV file (range-aware).
GET    /api/jobs/{job_id}/download       Download ZIP of all stems.
POST   /api/jobs/{job_id}/cancel         Cancel a running / queued job.
DELETE /api/jobs/{job_id}                Delete a job and its files.
GET    /api/models                       List available separation models.
GET    /api/health                       Health check.
"""
from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

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
        "name": "Electric Guitar",
        "label": "Guitar Isolation",
        "description": "Specialist electric guitar isolation using MelBand-Roformer. Best quality for guitar extraction.",
        "stems": ["electric_guitar", "no_electric_guitar"],
        "note": "Outputs the isolated guitar track and the rest of the mix (backing track).",
        "color": "#f59e0b",
        "icon": "guitar",
    },
    {
        "id": "htdemucs_ft",
        "name": "4-Stem Split (High Quality)",
        "label": "Vocals · Drums · Bass · Other",
        "description": "Separate a track into 4 stems using Facebook's htdemucs fine-tuned model. High accuracy, but slower on CPU.",
        "stems": ["vocals", "drums", "bass", "other", "backing_track"],
        "note": "'Other' contains keys, synths, and anything not explicitly separated.",
        "color": "#8b5cf6",
        "icon": "waveform",
    },
    {
        "id": "mdx_extra",
        "name": "4-Stem Split (Fast / CPU)",
        "label": "Vocals · Drums · Bass · Other",
        "description": "Uses the MDX Extra model for much faster processing on CPU with slightly less accuracy.",
        "stems": ["vocals", "drums", "bass", "other", "backing_track"],
        "note": "Best choice if you don't have a GPU and need results quickly.",
        "color": "#ef4444",
        "icon": "zap",
    },
    {
        "id": "htdemucs_6s",
        "name": "6-Stem Split",
        "label": "Vocals · Drums · Bass · Guitar · Piano · Other",
        "description": "Separate a track into 6 stems — adds guitar and piano to the basic 4-stem split.",
        "stems": ["vocals", "drums", "bass", "guitar", "piano", "other", "backing_track"],
        "note": "Most detailed separation. Takes longer to process.",
        "color": "#06b6d4",
        "icon": "stems",
    },
    {
        "id": "vocal_hq",
        "name": "Vocal Isolator",
        "label": "Vocals + Instrumental",
        "description": "Extract vocals and get a clean instrumental track using htdemucs.",
        "stems": ["vocals", "backing_track", "drums", "bass", "other"],
        "note": "Optimised for clean vocal extraction and karaoke-style backing tracks.",
        "color": "#10b981",
        "icon": "mic",
    },
]

# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok", "timestamp": time.time()}


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


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """Server-Sent Events endpoint — push status updates to client."""
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    async def event_generator():
        last_status = None
        last_detail = None
        while True:
            if await request.is_disconnected():
                break

            current_job = job_service.get_job(job_id)
            if current_job is None:
                yield f"data: {json.dumps({'status': 'deleted'})}\n\n"
                break

            # Only send if something changed
            if current_job.status != last_status or current_job.stage_detail != last_detail:
                last_status = current_job.status
                last_detail = current_job.stage_detail
                payload = _job_response(current_job)
                yield f"data: {json.dumps(payload)}\n\n"

            # Stop streaming when job is done
            if current_job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a queued or running job."""
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
        raise HTTPException(status_code=409, detail=f"Job already finished: {job.status}")
    # Mark as failed (worker checks this flag)
    job_service.cancel_job(job_id)
    return {"cancelled": True, "job_id": job_id}


@router.get("/jobs/{job_id}/stems/{stem_name}")
async def get_stem(job_id: str, stem_name: str, request: Request):
    job = job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=409, detail=f"Job not completed (status={job.status})")

    stem_path = job.stem_paths.get(stem_name)
    if stem_path is None or not stem_path.exists():
        raise HTTPException(status_code=404, detail=f"Stem '{stem_name}' not found")

    # Use FileResponse which handles Range requests automatically
    return FileResponse(
        str(stem_path),
        media_type="audio/wav",
        filename=f"{job.input_filename}_{stem_name}.wav",
        headers={"Accept-Ranges": "bytes"},
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
        "created_at": job.created_at,
        "finished_at": job.finished_at,
        "download_url": (
            f"/api/jobs/{job.id}/download"
            if job.status == JobStatus.COMPLETED
            else None
        ),
    }
