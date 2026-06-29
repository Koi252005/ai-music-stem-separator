"""app/main.py — FastAPI application entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.routes.jobs import router as jobs_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)

app = FastAPI(
    title="AI Music Stem Separator",
    description=(
        "Tách nhạc cụ từ bài hát bằng AI — "
        "Đồ án môn Trí tuệ nhân tạo"
    ),
    version="1.0.0",
)

# ── Static files ──────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_TEMPLATE_PATH = _HERE / "templates" / "index.html"

app.mount(
    "/static",
    StaticFiles(directory=str(_HERE / "static")),
    name="static",
)

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(jobs_router)


# ── Frontend ──────────────────────────────────────────────────────────────────
# NOTE: Jinja2Templates has a dict-key cache bug on Python 3.14+.
# Since index.html has no server-side template variables (all logic is in JS),
# we serve it as a plain static file to avoid the incompatibility.
@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(content=_TEMPLATE_PATH.read_text(encoding="utf-8"))


@app.get("/health")
async def health():
    return {"status": "ok"}

