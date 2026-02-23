"""
ArXiviz Backend API - FastAPI Entry Point

Run with: uvicorn main:app --reload --port 8000
Docs at: http://localhost:8000/docs
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables BEFORE any local imports
# (rendering/storage.py reads STORAGE_MODE at import time)
load_dotenv(Path(__file__).resolve().parent / ".env")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Set specific logger levels
logging.getLogger("rendering").setLevel(logging.INFO)
logging.getLogger("jobs").setLevel(logging.INFO)
logging.getLogger("agents").setLevel(logging.INFO)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse

from api.routes import router as api_router
from db import init_db
from utils.domain_utils import get_branding, DOMAIN_CONFIG


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    # Startup: Initialize database
    print("Initializing database...")
    await init_db()
    print("Database ready!")
    yield
    # Shutdown: cleanup if needed
    print("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="ArXiviz API",
    description="Transform arXiv papers into animated visual explanations",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for hackathon development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API router
app.include_router(api_router)


@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return RedirectResponse(url="/docs")


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("API_HOST", "0.0.0.0")
    # Support PORT (Render, Railway, Fly) and API_PORT (local)
    port = int(os.getenv("PORT") or os.getenv("API_PORT", "8000"))

    uvicorn.run("main:app", host=host, port=port, reload=True)


# === Multi-domain branding middleware ===

@app.middleware("http")
async def add_branding(request: Request, call_next):
    """Inject branding info into request state based on domain."""
    host = request.headers.get("host", "").split(":")[0].lower()
    branding = get_branding(host)
    request.state.branding = branding
    request.state.host = host
    response = await call_next(request)
    return response


@app.get("/api/branding")
async def get_current_branding(request: Request):
    """Get branding for current domain."""
    branding = getattr(request.state, "branding", get_branding("rxivisual.com"))
    return branding
