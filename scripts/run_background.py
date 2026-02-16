#!/usr/bin/env python3
"""
Background runner for AI Daily News Bot.
Runs the scheduler independently without FastAPI server.

Usage:
    python scripts/run_background.py              # Run in foreground
    python scripts/run_background.py --daemon     # Run as daemon (background)
    python scripts/run_background.py --once       # Run pipeline once and exit
"""

import asyncio
import sys
import signal
import logging
import platform
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings
from app.logging_config import setup_logging


logger = logging.getLogger(__name__)


class BackgroundRunner:
    """Background runner that manages scheduled tasks."""

    def __init__(self):
        self.running = False
        self.scheduler = None

    async def run_collectors(self):
        """Run information collection."""
        logger.info("Starting collection...")
        try:
            from scripts.run_collector import run_collectors
            await run_collectors()
            logger.info("Collection completed")
        except Exception as e:
            logger.error(f"Collection failed: {e}")

    async def run_processor(self):
        """Run AI processing."""
        logger.info("Starting processing...")
        try:
            from scripts.run_processor import run_processor
            await run_processor()
            logger.info("Processing completed")
        except Exception as e:
            logger.error(f"Processing failed: {e}")

    async def run_generator(self):
        """Run report generation."""
        logger.info("Starting report generation...")
        try:
            from scripts.run_generator import run_generator
            await run_generator(send_email=settings.email_enabled)
            logger.info("Report generation completed")
        except Exception as e:
            logger.error(f"Report generation failed: {e}")

    async def run_pipeline_once(self):
        """Run the full pipeline once and exit."""
        logger.info("=" * 60)
        logger.info("Running full pipeline (once)")
        logger.info("=" * 60)

        await self.run_collectors()
        await self.run_processor()
        await self.run_generator()

        logger.info("=" * 60)
        logger.info("Pipeline completed")
        logger.info("=" * 60)

    async def start_scheduler(self):
        """Start the scheduler for continuous operation."""
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.interval import IntervalTrigger
        from apscheduler.triggers.cron import CronTrigger

        self.scheduler = AsyncIOScheduler()

        # Collection job - every N hours
        self.scheduler.add_job(
            self.run_collectors,
            trigger=IntervalTrigger(hours=settings.collect_interval_hours),
            id="collect_job",
            name="Information Collection",
            replace_existing=True,
        )
        logger.info(f"Scheduled collection: every {settings.collect_interval_hours} hours")

        # Full pipeline (with email) - daily at specified hour
        async def daily_pipeline():
            await self.run_collectors()
            await self.run_processor()
            await self.run_generator()

        self.scheduler.add_job(
            daily_pipeline,
            trigger=CronTrigger(hour=settings.report_generation_hour, minute=0),
            id="daily_report_job",
            name="Daily Report with Email",
            replace_existing=True,
        )
        logger.info(f"Scheduled daily report: every day at {settings.report_generation_hour}:00")

        self.scheduler.start()
        self.running = True

        logger.info("=" * 60)
        logger.info("Background runner started")
        logger.info(f"Collection interval: {settings.collect_interval_hours} hours")
        logger.info(f"Daily report time: {settings.report_generation_hour}:00")
        logger.info(f"Email enabled: {settings.email_enabled}")
        logger.info("=" * 60)
        logger.info("Press Ctrl+C to stop")

        # Keep running
        try:
            while self.running:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            self.scheduler.shutdown()
            logger.info("Scheduler stopped")

    def stop(self):
        """Stop the runner."""
        self.running = False


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Daily News Bot Background Runner")
    parser.add_argument("--once", action="store_true", help="Run pipeline once and exit")
    parser.add_argument("--collect", action="store_true", help="Run collection only")
    parser.add_argument("--process", action="store_true", help="Run processing only")
    parser.add_argument("--generate", action="store_true", help="Run generation only")

    args = parser.parse_args()

    # Setup logging
    setup_logging()

    runner = BackgroundRunner()

    # Handle shutdown signals
    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        runner.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    # SIGTERM is not available on Windows
    if platform.system() != 'Windows':
        signal.signal(signal.SIGTERM, signal_handler)

    # Run based on arguments
    if args.collect:
        await runner.run_collectors()
    elif args.process:
        await runner.run_processor()
    elif args.generate:
        await runner.run_generator()
    elif args.once:
        await runner.run_pipeline_once()
    else:
        await runner.start_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
