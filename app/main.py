"""app/main.py — FastAPI application entry point."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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

# ── Static files & templates ──────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent

app.mount(
    "/static",
    StaticFiles(directory=str(_HERE / "static")),
    name="static",
)

templates = Jinja2Templates(directory=str(_HERE / "templates"))

# ── API routes ────────────────────────────────────────────────────────────────
app.include_router(jobs_router)


# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    return {"status": "ok"}
