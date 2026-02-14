"""
FastAPI main application for AI Daily News Bot.
"""

from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.scheduler import scheduler_manager, start_scheduler, stop_scheduler


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


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "AI Daily News Bot",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# Scheduler status endpoint
@app.get("/api/scheduler/status")
async def scheduler_status():
    """Get scheduler status."""
    jobs = scheduler_manager.get_jobs()

    return {
        "running": scheduler_manager._running,
        "jobs": [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in jobs
        ],
    }


# Manual trigger endpoints
@app.post("/api/scheduler/trigger/{job_id}")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job."""
    scheduler_manager.trigger_job(job_id)
    return {"message": f"Job {job_id} triggered"}


# Import and include API routes
from app.api.routes import router as api_router
app.include_router(api_router, prefix="/api")
