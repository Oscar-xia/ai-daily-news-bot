"""
Scheduler module for AI Daily News Bot.
Handles periodic tasks using APScheduler.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from app.config import settings


logger = logging.getLogger(__name__)


class SchedulerManager:
    """Manages scheduled tasks for AI Daily News Bot."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._running = False

    async def run_collectors(self):
        """Run information collection task."""
        logger.info("Starting scheduled collection task")

        try:
            # Import here to avoid circular imports
            from scripts.run_collector import run_collectors
            await run_collectors()
            logger.info("Collection task completed")
        except Exception as e:
            logger.error(f"Collection task failed: {e}")

    async def run_processor(self):
        """Run AI processing task."""
        logger.info("Starting scheduled processing task")

        try:
            from scripts.run_processor import run_processor
            await run_processor()
            logger.info("Processing task completed")
        except Exception as e:
            logger.error(f"Processing task failed: {e}")

    async def run_generator(self):
        """Run report generation task."""
        logger.info("Starting scheduled report generation task")

        try:
            from scripts.run_generator import run_generator
            await run_generator()
            logger.info("Report generation task completed")
        except Exception as e:
            logger.error(f"Report generation task failed: {e}")

    async def run_full_pipeline(self):
        """Run the full pipeline: collect -> process -> generate."""
        logger.info("Starting full pipeline")

        await self.run_collectors()
        await self.run_processor()
        await self.run_generator()

        logger.info("Full pipeline completed")

    def setup_jobs(self):
        """Setup scheduled jobs based on configuration."""
        # Collection job - every N hours
        self.scheduler.add_job(
            self.run_collectors,
            trigger=IntervalTrigger(hours=settings.collect_interval_hours),
            id="collect_job",
            name="Information Collection",
            replace_existing=True,
        )
        logger.info(f"Scheduled collection job: every {settings.collect_interval_hours} hours")

        # Report generation job - daily at specified hour
        self.scheduler.add_job(
            self.run_full_pipeline,
            trigger=CronTrigger(hour=settings.report_generation_hour, minute=0),
            id="daily_report_job",
            name="Daily Report Generation",
            replace_existing=True,
        )
        logger.info(f"Scheduled daily report job: every day at {settings.report_generation_hour}:00")

    def start(self):
        """Start the scheduler."""
        if self._running:
            logger.warning("Scheduler is already running")
            return

        if not settings.scheduler_enabled:
            logger.info("Scheduler is disabled in configuration")
            return

        self.setup_jobs()
        self.scheduler.start()
        self._running = True
        logger.info("Scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if not self._running:
            return

        self.scheduler.shutdown()
        self._running = False
        logger.info("Scheduler stopped")

    def get_jobs(self):
        """Get list of scheduled jobs."""
        return self.scheduler.get_jobs()

    def trigger_job(self, job_id: str):
        """Manually trigger a job."""
        job = self.scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            logger.info(f"Triggered job: {job_id}")
        else:
            logger.warning(f"Job not found: {job_id}")


# Global scheduler instance
scheduler_manager = SchedulerManager()


async def start_scheduler():
    """Start the scheduler (convenience function)."""
    scheduler_manager.start()


async def stop_scheduler():
    """Stop the scheduler (convenience function)."""
    scheduler_manager.stop()
