#!/usr/bin/env python3
"""
Run generator script.
Generate daily report from processed items.
"""

import asyncio
import sys
from pathlib import Path
from datetime import date, datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models.schemas import ProcessedItem, RawItem, Report, ReportItem
from app.generators.report_generator import ReportGenerator


async def run_generator(
    report_date: Optional[date] = None,
    min_score: int = 50,
    output_dir: str = "output/reports"
):
    """Generate daily report.

    Args:
        report_date: Date for the report (defaults to today)
        min_score: Minimum score threshold for items
        output_dir: Output directory for markdown file
    """
    report_date = report_date or date.today()
    date_str = report_date.strftime("%Y-%m-%d")

    print("=" * 60)
    print("AI Daily News Bot - Report Generator")
    print("=" * 60)
    print(f"Report date: {date_str}")
    print(f"Minimum score: {min_score}")
    print()

    # Initialize generator
    generator = ReportGenerator()

    # Get processed items from today
    async with async_session() as session:
        # Get items processed today
        today_start = datetime.combine(report_date, datetime.min.time())

        query = (
            select(ProcessedItem)
            .join(RawItem)
            .where(ProcessedItem.approved == True)
            .where(ProcessedItem.score >= min_score)
            .where(ProcessedItem.processed_at >= today_start)
            .order_by(ProcessedItem.score.desc())
        )

        result = await session.execute(query)
        items = result.scalars().all()

        # Load raw items
        for item in items:
            raw_result = await session.execute(
                select(RawItem).where(RawItem.id == item.raw_item_id)
            )
            item.raw_item = raw_result.scalars().first()

    if not items:
        print("No approved items found for today.")
        print("Run 'python scripts/run_processor.py' first to process items.")

        # Generate empty report
        report_content = generator._generate_empty_report(date_str)
    else:
        print(f"Found {len(items)} approved items.")

        # Generate report
        print("Generating report...")
        report_content = await generator.generate(items, report_date)

    # Save to database
    async with async_session() as session:
        # Check if report already exists
        existing = await session.execute(
            select(Report).where(Report.report_date == report_date)
        )
        report = existing.scalars().first()

        if report:
            print(f"Updating existing report...")
            report.content = report_content
            report.title = f"AI Daily News - {date_str}"
        else:
            print("Creating new report...")
            report = Report(
                report_date=report_date,
                title=f"AI Daily News - {date_str}",
                content=report_content,
                status="draft",
            )
            session.add(report)

        await session.commit()

        # Add report items
        if items:
            # Clear existing report items
            await session.execute(
                select(ReportItem).where(ReportItem.report_id == report.id)
            )

            for i, item in enumerate(items):
                report_item = ReportItem(
                    report_id=report.id,
                    processed_item_id=item.id,
                    order_index=i,
                )
                session.add(report_item)

            await session.commit()

    # Save to file
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / f"{date_str}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report_content)

    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Report generated: {output_file}")
    print(f"Items included: {len(items)}")
    print(f"Report ID: {report.id}")
    print(f"Status: {report.status}")
    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generate daily report")
    parser.add_argument(
        "--date", "-d",
        type=str,
        help="Report date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--min-score", "-m",
        type=int,
        default=50,
        help="Minimum score threshold"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default="output/reports",
        help="Output directory"
    )

    args = parser.parse_args()

    report_date = None
    if args.date:
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    asyncio.run(run_generator(report_date, args.min_score, args.output))


if __name__ == "__main__":
    main()
