"""run.py — Start the development server.

Usage:
    python run.py              # default: http://0.0.0.0:8000
    python run.py --port 5000
"""
import argparse
import uvicorn

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Run the AI Music Stem Separator server.")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--reload", action="store_true", help="Hot-reload on code changes.")
    args = p.parse_args()

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )
