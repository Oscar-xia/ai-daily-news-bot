#!/usr/bin/env python3
"""
Run collectors script.
Manually trigger information collection from various sources.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models.schemas import Source, RawItem
from app.collectors.rss_collector import RSSCollector
from app.collectors.twitter_collector import TwitterCollector
from app.collectors.search_collector import SearchCollector
from app.processors.deduplicator import Deduplicator


async def collect_from_source(
    source: Source,
    collector,
    deduplicator: Deduplicator
) -> tuple:
    """Collect from a single source.

    Returns:
        Tuple of (collected_count, duplicate_count, error)
    """
    try:
        source_config = {
            "name": source.name,
            "url": source.url,
            "config": source.config,
        }

        items = await collector.collect(source_config)

        # Check for duplicates against existing items
        unique_items, duplicates = deduplicator.deduplicate(items)

        # Store unique items
        stored_count = 0
        async with async_session() as session:
            for item in unique_items:
                # Check if URL already exists
                if item.url:
                    existing = await session.execute(
                        select(RawItem).where(RawItem.url == item.url)
                    )
                    if existing.scalars().first():
                        continue

                raw_item = RawItem(
                    source_id=source.id,
                    title=item.title,
                    content=item.content,
                    url=item.url,
                    author=item.author,
                    published_at=item.published_at,
                    category=item.category,
                    status="pending",
                )
                session.add(raw_item)
                stored_count += 1

            # Update source last_fetched_at
            source.last_fetched_at = datetime.utcnow()
            session.add(source)

            await session.commit()

        return len(items), len(duplicates) + (len(items) - len(unique_items) - stored_count), None

    except Exception as e:
        return 0, 0, str(e)


async def run_collectors(
    source_type: Optional[str] = None,
    source_id: Optional[int] = None
):
    """Run collectors.

    Args:
        source_type: Filter by type (rss, twitter, search, or None for all)
        source_id: Filter by specific source ID
    """
    print("=" * 60)
    print("AI Daily News Bot - Information Collection")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize collectors
    rss_collector = RSSCollector()
    twitter_collector = TwitterCollector()
    search_collector = SearchCollector()

    # Initialize deduplicator
    deduplicator = Deduplicator()

    # Load existing items for deduplication
    async with async_session() as session:
        result = await session.execute(
            select(RawItem).where(RawItem.fetched_at >= datetime.utcnow().replace(hour=0, minute=0, second=0))
        )
        existing_items = result.scalars().all()
        deduplicator.add_existing_items(list(existing_items))

    # Get sources
    async with async_session() as session:
        query = select(Source).where(Source.enabled == True)

        if source_type:
            query = query.where(Source.type == source_type)
        if source_id:
            query = query.where(Source.id == source_id)

        result = await session.execute(query)
        sources = result.scalars().all()

    if not sources:
        print("No sources found to collect from.")
        return

    print(f"Found {len(sources)} sources to collect from.")
    print()

    # Collect from each source
    total_collected = 0
    total_duplicates = 0
    errors = []

    for source in sources:
        print(f"Collecting from [{source.type}] {source.name}...")

        # Select collector based on type
        if source.type == "rss":
            collector = rss_collector
        elif source.type == "twitter":
            collector = twitter_collector
        elif source.type == "search":
            collector = search_collector
        else:
            print(f"  Unknown source type: {source.type}")
            continue

        collected, duplicates, error = await collect_from_source(
            source, collector, deduplicator
        )

        if error:
            print(f"  Error: {error}")
            errors.append((source.name, error))
        else:
            print(f"  Collected: {collected}, Duplicates: {duplicates}")
            total_collected += collected
            total_duplicates += duplicates

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Total collected: {total_collected}")
    print(f"Total duplicates: {total_duplicates}")
    print(f"Stored (unique): {total_collected - total_duplicates}")

    if errors:
        print(f"Errors: {len(errors)}")
        for name, error in errors:
            print(f"  - {name}: {error}")

    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run information collectors")
    parser.add_argument(
        "--type", "-t",
        choices=["rss", "twitter", "search", "all"],
        default="all",
        help="Source type to collect from"
    )
    parser.add_argument(
        "--source-id", "-s",
        type=int,
        help="Specific source ID to collect from"
    )

    args = parser.parse_args()

    source_type = None if args.type == "all" else args.type

    asyncio.run(run_collectors(source_type, args.source_id))


if __name__ == "__main__":
    main()
