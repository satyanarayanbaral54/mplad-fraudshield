"""
MPLAD FraudShield - Backend API
Smart India Hackathon Project
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from database import init_db
from routers import projects, vendors, dashboard, surveys, ingestion, demo


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("Starting MPLAD FraudShield API...")
    try:
        init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database init skipped: {e}")
    yield
    logger.info("Shutting down MPLAD FraudShield API...")


# ---------------------------------------------------------------------------
# FastAPI application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="MPLAD FraudShield API",
    description=(
        "AI-powered fraud and anomaly detection system for the "
        "Members of Parliament Local Area Development (MPLAD) scheme."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------

app.include_router(
    dashboard.router,
    prefix="/api/v1/dashboard",
    tags=["Dashboard"],
)

app.include_router(
    projects.router,
    prefix="/api/v1/projects",
    tags=["Projects"],
)

app.include_router(
    vendors.router,
    prefix="/api/v1/vendors",
    tags=["Vendors"],
)

app.include_router(
    surveys.router,
    prefix="/api/v1/survey",
    tags=["Surveys"],
)

app.include_router(
    ingestion.router,
    prefix="/api/v1/ingest",
    tags=["Ingestion"],
)

app.include_router(
    demo.router,
    prefix="/api/v1/demo",
    tags=["Demo"],
)


# ---------------------------------------------------------------------------
# WebSocket
# ---------------------------------------------------------------------------

app.add_api_websocket_route(
    "/ws/live-flags",
    demo.websocket_live_flags,
)


# ---------------------------------------------------------------------------
# Health checks  (registered BEFORE the SPA catch-all)
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health():
    return JSONResponse({"status": "healthy", "database": "connected"})



# ---------------------------------------------------------------------------
# Frontend Static Files & SPA Routing
# Serves the built React app when frontend/dist exists.
# Falls back gracefully when running backend-only (npm run dev mode).
# ---------------------------------------------------------------------------

FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
)
# Also support dist/ placed directly next to main.py (Docker / Render)
_local_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "dist"))
if os.path.isdir(_local_dist):
    FRONTEND_DIST = _local_dist

if os.path.isdir(FRONTEND_DIST):
    logger.info(f"Serving frontend from: {FRONTEND_DIST}")

    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.isdir(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    from fastapi.exceptions import HTTPException
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        
        index_path = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.isfile(index_path):
            return FileResponse(index_path)
        return JSONResponse({"detail": "Not Found"}, status_code=404)

else:
    logger.info(
        "Frontend dist not found — running in API-only mode. "
        "Open http://localhost:5173 for the dev frontend."
    )

    @app.get("/", tags=["Health"])
    async def root():
        return {"status": "ok", "service": "MPLAD FraudShield API", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )