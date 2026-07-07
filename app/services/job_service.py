"""app/services/job_service.py — In-memory job queue with background threading.

Each separation request gets a unique UUID job. Jobs are processed one at a
time per worker thread so GPU memory is never shared between concurrent jobs.
"""
from __future__ import annotations

import logging
import shutil
import threading
import time
import traceback
import uuid
import zipfile
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from app.config import OUTPUTS_DIR, UPLOADS_DIR

log = logging.getLogger(__name__)


class JobStatus(str, Enum):
    QUEUED = "queued"
    PREPROCESSING = "preprocessing"
    LOADING_MODEL = "loading_model"
    SEPARATING = "separating"
    POSTPROCESSING = "postprocessing"
    MIXING = "mixing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    id: str
    model_id: str
    device: str
    status: JobStatus = JobStatus.QUEUED
    stage_detail: str = ""
    error: Optional[str] = None
    stems: dict[str, str] = field(default_factory=dict)  # stem_name → relative URL
    stem_paths: dict[str, Path] = field(default_factory=dict)  # stem_name → Path
    zip_path: Optional[Path] = None
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    input_filename: str = ""  # original uploaded filename (sanitized)


class JobService:
    """Thread-safe in-memory store + background worker for separation jobs."""

    def __init__(self):
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._queue: list[str] = []
        self._cancelled: set[str] = set()  # job IDs marked for cancellation
        self._queue_event = threading.Event()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        # Cleanup thread removes old finished jobs every 10 minutes
        self._cleanup = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup.start()

    # ── Public API ────────────────────────────────────────────────────────────

    def create_job(
        self,
        model_id: str,
        device: str,
        input_filename: str,
        job_id: Optional[str] = None,
    ) -> Job:
        if job_id is None:
            job_id = str(uuid.uuid4())

        job = Job(
            id=job_id,
            model_id=model_id,
            device=device,
            input_filename=input_filename,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._queue.append(job_id)
        self._queue_event.set()
        log.info("Job %s queued: model=%s device=%s", job_id, model_id, device)
        return job

    def get_job(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def delete_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.pop(job_id, None)
        if job is None:
            return False
        # Clean up files
        job_upload = UPLOADS_DIR / job_id
        job_output = OUTPUTS_DIR / job_id
        for p in (job_upload, job_output):
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)
        return True

    def cancel_job(self, job_id: str) -> bool:
        """Request cancellation of a queued or in-progress job."""
        with self._lock:
            if job_id not in self._jobs:
                return False
            self._cancelled.add(job_id)
            job = self._jobs[job_id]
            if job.status in (JobStatus.QUEUED,):
                # Remove from queue immediately if not yet started
                try:
                    self._queue.remove(job_id)
                except ValueError:
                    pass
                job.status = JobStatus.FAILED
                job.error = "Cancelled by user."
                job.stage_detail = "Cancelled"
                job.finished_at = time.time()
        return True

    def all_jobs(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    # ── Background worker ─────────────────────────────────────────────────────

    def _run(self):
        """Continuously dequeue and process jobs."""
        while True:
            self._queue_event.wait()
            self._queue_event.clear()
            while True:
                with self._lock:
                    if not self._queue:
                        break
                    job_id = self._queue.pop(0)
                    job = self._jobs.get(job_id)
                if job is None:
                    continue
                self._process(job)

    def _process(self, job: Job):
        # Check if cancelled before starting
        with self._lock:
            if job.id in self._cancelled:
                job.status = JobStatus.FAILED
                job.error = "Cancelled by user."
                job.finished_at = time.time()
                return

        job.started_at = time.time()
        try:
            self._update(job, JobStatus.PREPROCESSING, "Preparing input file…")
            input_path = self._get_input_path(job)

            output_dir = OUTPUTS_DIR / job.id
            output_dir.mkdir(parents=True, exist_ok=True)

            separator = self._build_separator(job.model_id)

            def progress_callback(stage: str, detail: str):
                status_map = {
                    "loading_model": JobStatus.LOADING_MODEL,
                    "separating": JobStatus.SEPARATING,
                    "postprocessing": JobStatus.POSTPROCESSING,
                    "mixing": JobStatus.MIXING,
                }
                s = status_map.get(stage, JobStatus.SEPARATING)
                self._update(job, s, detail)

            stem_paths = separator.separate(
                input_path=input_path,
                output_dir=output_dir,
                device=job.device,
                progress_callback=progress_callback,
            )

            self._update(job, JobStatus.MIXING, "Building backing tracks…")
            mixing_paths = _build_mixes(stem_paths, output_dir)
            stem_paths.update(mixing_paths)

            self._update(job, JobStatus.POSTPROCESSING, "Packaging ZIP…")
            zip_path = self._make_zip(stem_paths, output_dir, job.id)

            with self._lock:
                job.stem_paths = stem_paths
                job.stems = {k: f"/api/jobs/{job.id}/stems/{k}" for k in stem_paths}
                job.zip_path = zip_path
                job.status = JobStatus.COMPLETED
                job.stage_detail = "Done"
                job.finished_at = time.time()

            elapsed = job.finished_at - job.started_at
            log.info("Job %s completed in %.1fs", job.id, elapsed)

        except Exception as exc:  # pylint: disable=broad-except
            tb = traceback.format_exc()
            log.error("Job %s failed:\n%s", job.id, tb)
            with self._lock:
                job.status = JobStatus.FAILED
                job.error = f"{type(exc).__name__}: {exc}"
                job.stage_detail = "Failed"
                job.finished_at = time.time()

    def _update(self, job: Job, status: JobStatus, detail: str = ""):
        with self._lock:
            job.status = status
            job.stage_detail = detail
        log.debug("Job %s → %s: %s", job.id, status, detail)

    def _get_input_path(self, job: Job) -> Path:
        upload_dir = UPLOADS_DIR / job.id
        if not upload_dir.exists():
            raise FileNotFoundError(
                f"Upload directory not found for job {job.id}: {upload_dir}"
            )
        candidates = list(upload_dir.iterdir())
        if not candidates:
            raise FileNotFoundError(f"No uploaded file found for job {job.id}")
        return candidates[0]

    def _build_separator(self, model_id: str):
        """Instantiate the correct separator for *model_id*."""
        if model_id == "guitar":
            from app.separators.guitar_separator import GuitarSeparator
            return GuitarSeparator()
        elif model_id in ("htdemucs_ft", "htdemucs_6s"):
            from app.separators.demucs_separator import DemucsSeparator
            return DemucsSeparator(model_id)
        elif model_id == "vocal_hq":
            # High-quality vocal = htdemucs_ft focused on vocal stem
            from app.separators.demucs_separator import DemucsSeparator
            return DemucsSeparator("htdemucs_ft")
        else:
            raise ValueError(f"Unknown model: {model_id}")

    def _make_zip(
        self, stem_paths: dict[str, Path], output_dir: Path, job_id: str
    ) -> Path:
        zip_path = output_dir / f"{job_id}_stems.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for stem_name, p in stem_paths.items():
                if p.exists():
                    zf.write(p, arcname=p.name)
        return zip_path

    def _cleanup_loop(self):
        """Remove completed/failed jobs older than 1 hour to free disk space."""
        TTL_SECONDS = 3600
        while True:
            time.sleep(600)  # check every 10 minutes
            now = time.time()
            to_delete = []
            with self._lock:
                for job_id, job in self._jobs.items():
                    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                        age = now - (job.finished_at or job.created_at)
                        if age > TTL_SECONDS:
                            to_delete.append(job_id)
            for job_id in to_delete:
                log.info("Auto-cleanup: removing expired job %s", job_id)
                self.delete_job(job_id)


# ── Mix helpers ───────────────────────────────────────────────────────────────

def _build_mixes(
    stem_paths: dict[str, Path], output_dir: Path
) -> dict[str, Path]:
    """Create backing_track and instrumental from available stems."""
    import numpy as np
    import soundfile as sf

    mixes: dict[str, Path] = {}

    # Determine vocal stems to exclude
    vocal_stems = {"vocals"}

    non_vocal = [
        name for name in stem_paths
        if name not in vocal_stems and name not in ("backing_track", "instrumental")
    ]
    all_stems = [
        name for name in stem_paths
        if name not in ("backing_track", "instrumental")
    ]

    def _mix(names: list[str], out_name: str):
        """Sum the listed stems and write to output_dir/out_name.wav."""
        if not names:
            return
        arrays = []
        sr = None
        for n in names:
            p = stem_paths.get(n)
            if p is None or not p.exists():
                continue
            data, file_sr = sf.read(str(p), dtype="float32")
            if data.ndim == 1:
                data = np.stack([data, data], axis=1)
            arrays.append(data)
            sr = file_sr

        if not arrays or sr is None:
            return

        # Align lengths by zero-padding to longest
        max_len = max(a.shape[0] for a in arrays)
        padded = [
            np.pad(a, ((0, max_len - a.shape[0]), (0, 0)))
            for a in arrays
        ]
        mixed = np.sum(padded, axis=0)

        # Prevent clipping
        peak = float(np.abs(mixed).max())
        if peak > 1.0:
            mixed = mixed / peak

        out_path = output_dir / f"{out_name}.wav"
        sf.write(str(out_path), mixed, sr, subtype="PCM_16")
        mixes[out_name] = out_path

    if non_vocal:
        _mix(non_vocal, "backing_track")
    # Instrumental = same as backing track when there's only one vocal stem
    # (htdemucs has a single "vocals" output, not lead+backing).
    if non_vocal:
        _mix(non_vocal, "instrumental")

    return mixes


# ── Singleton ─────────────────────────────────────────────────────────────────
job_service = JobService()
