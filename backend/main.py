"""
MPLAD FraudShield - Backend API
Smart India Hackathon Project
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
# Health checks
# ---------------------------------------------------------------------------

@app.get("/", tags=["Health"])
async def root():
    return {"status": "ok", "service": "MPLAD FraudShield API", "version": "1.0.0"}


@app.get("/health", tags=["Health"])
async def health():
    return JSONResponse(
        {
            "status": "healthy",
            "database": "connected",
        }
    )


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