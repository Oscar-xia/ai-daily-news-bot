"""
FastAPI main application for AI Daily News Bot.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.config import settings
from app.scheduler import scheduler_manager, start_scheduler, stop_scheduler


# Paths
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    print("Starting AI Daily News Bot...")

    # Start scheduler if enabled
    if settings.scheduler_enabled:
        await start_scheduler()
        print("Scheduler started")

    yield

    # Shutdown
    print("Shutting down AI Daily News Bot...")
    await stop_scheduler()
    print("Scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="AI Daily News Bot",
    description="AI + Investment + Web3 Daily News Generator",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "scheduler_enabled": settings.scheduler_enabled,
    }


# Scheduler status endpoint
@app.get("/api/scheduler/status")
async def scheduler_status():
    """Get scheduler status."""
    jobs = scheduler_manager.get_jobs() if scheduler_manager._running else []

    next_collect = None
    next_report = None

    for job in jobs:
        if "collect" in job.id:
            next_collect = str(job.next_run_time) if job.next_run_time else None
        elif "report" in job.id or "generate" in job.id:
            next_report = str(job.next_run_time) if job.next_run_time else None

    return {
        "running": scheduler_manager._running,
        "next_collect": next_collect or "-",
        "last_collect": "-",  # TODO: track in database
        "next_report": next_report or "-",
        "last_report": "-",  # TODO: track in database
    }


# Manual trigger endpoints
@app.post("/api/scheduler/trigger/{job_id}")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job."""
    if scheduler_manager._running:
        scheduler_manager.trigger_job(job_id)
    return {"message": f"Job {job_id} triggered"}


# Import and include API routes
from app.api.routes import router as api_router
app.include_router(api_router, prefix="/api")


# Serve frontend
@app.get("/")
async def serve_frontend():
    """Serve frontend index.html."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "name": "AI Daily News Bot",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "message": "Frontend not found. Please build the frontend first.",
    }


# Fallback to index.html for SPA routing
@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve SPA fallback."""
    # Don't intercept API routes
    if path.startswith("api/") or path.startswith("docs") or path.startswith("openapi"):
        return None

    # Serve static files if they exist
    file_path = FRONTEND_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    # Fallback to index.html for SPA routing
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)

    return {"error": "Not found"}
