"""
FastAPI Main Application Entrypoint for UK Day-Ahead Wind Power Trading Desk.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.config import settings
from backend.app.data_store import data_store
from backend.app.api.endpoints import router as api_router

# Configure logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler: loads BMRS datasets at startup."""
    logger.info("Initializing %s...", settings.PROJECT_NAME)
    try:
        data_store.load(settings.DATA_DIR)
    except Exception as e:
        logger.error("Failed to load initial data from %s: %s", settings.DATA_DIR, e)
    yield
    logger.info("Shutting down %s.", settings.PROJECT_NAME)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Full-Stack Quantitative Intelligence & Trading Evaluation API for UK Energy Utility's "
        "Day-Ahead Wind Power Trading Desk. Exclusively integrates Elexon BMRS FUELHH (Actuals) "
        "and WINDFOR (Forecasts) data for January 2026."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS is needed for the separate local Vite dev server. Vercel serves the
# frontend and function from the same origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router
app.include_router(api_router, prefix="/api")


@app.get("/", tags=["System"])
def root():
    return {
        "service": settings.PROJECT_NAME,
        "docs": "/docs",
        "health": "/api/health",
        "scope": "January 2026 UK Day-Ahead Wind Power"
    }
