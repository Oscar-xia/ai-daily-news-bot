#!/usr/bin/env python3
"""
CLI tool for AI Daily News Bot.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from datetime import datetime

from app.database import async_session
from app.models.schemas import Source
from sqlalchemy import select


@click.group()
def cli():
    """AI Daily News Bot CLI."""
    pass


# =============================================================================
# Source commands
# =============================================================================

@cli.group()
def source():
    """Manage information sources."""
    pass


@source.command("list")
def list_sources():
    """List all sources."""
    async def _list():
        async with async_session() as session:
            result = await session.execute(select(Source))
            sources = result.scalars().all()

            if not sources:
                click.echo("No sources found.")
                return

            click.echo(f"Found {len(sources)} sources:\n")
            for s in sources:
                status = "✓" if s.enabled else "✗"
                click.echo(f"  [{status}] {s.id:2}. [{s.type:7}] {s.name}")
                if s.url:
                    click.echo(f"          {s.url[:60]}...")

    asyncio.run(_list())


@source.command("add")
@click.option("--name", "-n", required=True, help="Source name")
@click.option("--type", "-t", "source_type", required=True, type=click.Choice(["rss", "twitter", "search"]), help="Source type")
@click.option("--url", "-u", required=True, help="Source URL or query")
@click.option("--category", "-c", default="mixed", help="Category (ai/investment/web3/mixed)")
def add_source(name, source_type, url, category):
    """Add a new source."""
    import json

    async def _add():
        async with async_session() as session:
            source = Source(
                name=name,
                type=source_type,
                url=url,
                config=json.dumps({"category": category}),
                enabled=True,
            )
            session.add(source)
            await session.commit()
            click.echo(f"✓ Source added: {name} (ID: {source.id})")

    asyncio.run(_add())


@source.command("disable")
@click.argument("source_id", type=int)
def disable_source(source_id):
    """Disable a source."""
    async def _disable():
        async with async_session() as session:
            result = await session.execute(select(Source).where(Source.id == source_id))
            source = result.scalars().first()

            if not source:
                click.echo(f"Source {source_id} not found.")
                return

            source.enabled = False
            await session.commit()
            click.echo(f"✓ Source {source_id} disabled.")

    asyncio.run(_disable())


# =============================================================================
# Collection commands
# =============================================================================

@cli.command()
@click.option("--type", "-t", "source_type", type=click.Choice(["rss", "twitter", "search", "all"]), default="all")
@click.option("--source-id", "-s", type=int, help="Specific source ID")
def collect(source_type, source_id):
    """Run information collection."""
    from scripts.run_collector import run_collectors

    st = None if source_type == "all" else source_type
    asyncio.run(run_collectors(st, source_id))


@cli.command()
@click.option("--limit", "-l", default=50, help="Max items to process")
@click.option("--min-score", "-m", default=0, help="Minimum score threshold")
def process(limit, min_score):
    """Run AI processing."""
    from scripts.run_processor import run_processor
    asyncio.run(run_processor(None, min_score, limit))


@cli.command()
@click.option("--date", "-d", help="Report date (YYYY-MM-DD)")
@click.option("--min-score", "-m", default=50, help="Minimum score threshold")
@click.option("--send-email", "-e", is_flag=True, help="Send report via email")
def generate(date, min_score, send_email):
    """Generate daily report."""
    from scripts.run_generator import run_generator

    report_date = None
    if date:
        report_date = datetime.strptime(date, "%Y-%m-%d").date()

    asyncio.run(run_generator(report_date, min_score, 15, "output/reports", send_email))


# =============================================================================
# Pipeline command
# =============================================================================

@cli.command()
@click.option("--min-score", "-m", default=50, help="Minimum score threshold")
@click.option("--send-email", "-e", is_flag=True, help="Send report via email after generation")
def pipeline(min_score, send_email):
    """Run full pipeline: collect -> process -> generate."""
    async def _pipeline():
        from scripts.run_collector import run_collectors
        from scripts.run_processor import run_processor
        from scripts.run_generator import run_generator

        click.echo("=" * 50)
        click.echo("Running full pipeline...")
        click.echo("=" * 50)

        click.echo("\n[1/3] Collecting...")
        await run_collectors()

        click.echo("\n[2/3] Processing...")
        await run_processor(None, min_score, 100)

        click.echo("\n[3/3] Generating report...")
        await run_generator(None, min_score, 15, "output/reports", send_email)

        click.echo("\n" + "=" * 50)
        click.echo("Pipeline completed!")

    asyncio.run(_pipeline())


# =============================================================================
# Status command
# =============================================================================

@cli.command()
def status():
    """Show system status."""
    async def _status():
        from sqlalchemy import func
        from app.models.schemas import RawItem, ProcessedItem, Report

        async with async_session() as session:
            # Counts
            sources_count = await session.execute(select(func.count()).select_from(Source))
            raw_count = await session.execute(select(func.count()).select_from(RawItem))
            pending_count = await session.execute(select(func.count()).select_from(RawItem).where(RawItem.status == "pending"))
            processed_count = await session.execute(select(func.count()).select_from(ProcessedItem))
            reports_count = await session.execute(select(func.count()).select_from(Report))

            click.echo("=" * 50)
            click.echo("AI Daily News Bot - Status")
            click.echo("=" * 50)
            click.echo(f"\nSources:      {sources_count.scalar()}")
            click.echo(f"Raw Items:    {raw_count.scalar()}")
            click.echo(f"  Pending:    {pending_count.scalar()}")
            click.echo(f"Processed:    {processed_count.scalar()}")
            click.echo(f"Reports:      {reports_count.scalar()}")

    asyncio.run(_status())


# =============================================================================
# Email command
# =============================================================================

@cli.command()
@click.option("--test", "-t", is_flag=True, help="Send test email")
@click.option("--latest", "-l", is_flag=True, help="Send latest report via email")
def email(test, latest):
    """Email notification commands."""
    from app.notification.email_sender import send_email, send_report, is_email_configured
    from app.config import settings

    if not is_email_configured():
        click.echo("Email not configured. Please set EMAIL_ENABLED, EMAIL_SENDER, and EMAIL_PASSWORD in .env")
        return

    click.echo(f"Email configured: {settings.email_sender}")
    click.echo(f"Receivers: {settings.email_receiver_list}")

    if test:
        click.echo("\nSending test email...")
        content = """# 测试邮件

这是一封来自 **AI技术日报** 的测试邮件。

如果你收到这封邮件，说明邮件配置成功！

---
*发送时间: {}*
""".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

        success = send_email(content, "AI技术日报 - 测试邮件")
        if success:
            click.echo("✓ Test email sent successfully!")
        else:
            click.echo("✗ Failed to send test email")

    elif latest:
        from pathlib import Path
        report_file = Path("output/reports") / f"{datetime.now().strftime('%Y-%m-%d')}_latest.md"

        if not report_file.exists():
            click.echo(f"Latest report not found: {report_file}")
            return

        content = report_file.read_text(encoding='utf-8')
        date_str = datetime.now().strftime('%Y-%m-%d')

        click.echo(f"\nSending latest report ({date_str})...")
        success = send_report(content, date_str)
        if success:
            click.echo("✓ Report sent successfully!")
        else:
            click.echo("✗ Failed to send report")

    else:
        click.echo("\nUsage:")
        click.echo("  python scripts/cli.py email --test     # Send test email")
        click.echo("  python scripts/cli.py email --latest   # Send latest report")


if __name__ == "__main__":
    cli()
