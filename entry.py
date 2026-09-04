import os
import sys

# Ensure root directory is on sys.path
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402

# 1. Lightweight root app for near-instant startup (<50ms) to satisfy Cloudflare startup CPU limit
app = FastAPI(title="EquiGrade API (Cloudflare Worker)", version="1.0.0")


@app.get("/")
async def root():
    return {
        "status": "ok",
        "service": "EquiGrade API (Cloudflare Worker)",
        "runtime": "Pyodide / WebAssembly",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "service": "equigrade-backend-cloudflare"}


@app.get("/api/v1/health")
async def api_v1_health():
    return {"status": "ok", "service": "equigrade-backend-cloudflare"}


@app.get("/api/info")
async def api_info():
    return {"message": "EquiGrade API Running on Cloudflare Worker"}


# 2. Lazy loader for the full monolithic backend
_full_app = None
_load_error = None


def get_full_app():
    global _full_app, _load_error
    if _full_app is None and _load_error is None:
        try:
            from main import app as monolith_app

            _full_app = monolith_app
        except Exception as e:
            _load_error = str(e)
            print(f"Error lazy loading monolithic backend: {e}")
    return _full_app


# 3. Custom ASGI router delegating requests
async def asgi_handler(scope, receive, send):
    if scope.get("type") == "http":
        path = scope.get("path", "")
        # Fast path for baseline health & root endpoints
        if path in (
            "/",
            "/health",
            "/health/",
            "/api/v1/health",
            "/api/v1/health/",
            "/api/info",
        ):
            await app(scope, receive, send)
            return

        # Lazy load full application on first request
        full_app = get_full_app()
        if full_app is not None:
            await full_app(scope, receive, send)
            return
        elif _load_error is not None:
            response = JSONResponse(
                status_code=500,
                content={
                    "status": "error",
                    "message": "Failed to load backend monolith",
                    "error": _load_error,
                },
            )
            await response(scope, receive, send)
            return

    await app(scope, receive, send)


# 4. Cloudflare Python Workers ASGI handler
try:
    from workers import asgi

    Default = asgi.entrypoint(asgi_handler)
except ImportError:
    Default = asgi_handler  # type: ignore[assignment]
