#!/usr/bin/env python3
"""
RSS Collector Script.
Version 2.0 - 简化版，10路并发
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx
import feedparser
from sqlalchemy import select

from app.database import async_session
from app.models.schemas import Source, RawItem
from app.collectors.base import CollectedItem
from app.processors.deduplicator import Deduplicator
from app.config import settings


# 常量
FEED_FETCH_TIMEOUT_MS = 15_000
FEED_CONCURRENCY = 10


async def fetch_feed(source: Source) -> list[CollectedItem]:
    """Fetch and parse a single RSS feed."""
    items = []

    try:
        async with httpx.AsyncClient(timeout=FEED_FETCH_TIMEOUT_MS / 1000) as client:
            response = await client.get(
                source.url,
                follow_redirects=True,
                headers={
                    'User-Agent': 'AI-Daily-Digest/2.0 (RSS Reader)',
                    'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
                }
            )
            response.raise_for_status()

        feed = feedparser.parse(response.content)

        for entry in feed.entries:
            item = parse_entry(entry, source.name)
            if item:
                items.append(item)

    except Exception as e:
        print(f"  ✗ {source.name}: {e}")

    return items


def parse_entry(entry, source_name: str) -> CollectedItem | None:
    """Parse a feed entry into a CollectedItem."""
    title = entry.get('title', '')
    if not title:
        return None

    # Get URL
    url = entry.get('link', '')
    if not url:
        links = entry.get('links', [])
        if links:
            url = links[0].get('href', '')

    # Get content
    content = ""
    if 'content' in entry:
        content = entry.content[0].get('value', '')
    elif 'summary' in entry:
        content = entry.summary
    elif 'description' in entry:
        content = entry.description

    # Clean HTML
    import re
    import html as html_module
    content = re.sub(r'<[^>]+>', '', content)
    content = html_module.unescape(content)
    content = content.strip()[:2000]

    # Get author
    author = None
    if 'author' in entry:
        author = entry.author
    elif 'authors' in entry and entry.authors:
        author = entry.authors[0].get('name')

    # Get published date
    published_at = None
    if 'published_parsed' in entry and entry.published_parsed:
        try:
            published_at = datetime(*entry.published_parsed[:6])
        except (ValueError, TypeError):
            pass
    elif 'updated_parsed' in entry and entry.updated_parsed:
        try:
            published_at = datetime(*entry.updated_parsed[:6])
        except (ValueError, TypeError):
            pass

    return CollectedItem(
        title=title,
        url=url,
        content=content,
        author=author,
        published_at=published_at,
        source_name=source_name,
        source_type="rss",
        category=None,
    )


async def run_collectors(
    source_id: int = None,
    hours: int = 48,
):
    """Run RSS collection with 10-way concurrency.

    Args:
        source_id: Optional specific source ID to collect from
        hours: Time range for filtering (not used in collection, for reference)
    """
    print("=" * 60)
    print("AI Daily News Bot - RSS Collection (v2.0)")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Concurrency: {FEED_CONCURRENCY}")
    print()

    # Get sources
    async with async_session() as session:
        query = select(Source).where(Source.enabled == True, Source.type == 'rss')

        if source_id:
            query = query.where(Source.id == source_id)

        result = await session.execute(query)
        sources = result.scalars().all()

    if not sources:
        print("No RSS sources found.")
        return 0

    print(f"Found {len(sources)} RSS sources")
    print()

    # Collect with concurrency
    all_items = []
    success_count = 0
    fail_count = 0

    for i in range(0, len(sources), FEED_CONCURRENCY):
        batch = sources[i:i + FEED_CONCURRENCY]

        print(f"Fetching batch {i // FEED_CONCURRENCY + 1} ({len(batch)} sources)...")

        tasks = [fetch_feed(source) for source in batch]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for source, result in zip(batch, results):
            if isinstance(result, list):
                all_items.extend(result)
                if result:
                    success_count += 1
                    print(f"  ✓ {source.name}: {len(result)} items")
                else:
                    fail_count += 1
                    print(f"  ✗ {source.name}: no items")
            else:
                fail_count += 1
                print(f"  ✗ {source.name}: {result}")

        progress = min(i + FEED_CONCURRENCY, len(sources))
        print(f"Progress: {progress}/{len(sources)} sources ({success_count} ok, {fail_count} failed)")

    print()
    print(f"Fetched {len(all_items)} items from {success_count} sources")

    # Deduplicate
    print()
    print("Deduplicating...")
    deduplicator = Deduplicator()

    # Load existing URLs
    async with async_session() as session:
        result = await session.execute(
            select(RawItem.url).where(RawItem.url.isnot(None)).limit(10000)
        )
        existing_urls = set(row[0] for row in result.fetchall())

    # Simple URL dedup
    unique_items = []
    for item in all_items:
        if item.url and item.url in existing_urls:
            continue
        if item.url:
            existing_urls.add(item.url)
        unique_items.append(item)

    print(f"After dedup: {len(unique_items)} unique items")

    # Filter by time - only keep items within 48h
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    recent_items = [
        item for item in unique_items
        if item.published_at and item.published_at >= cutoff
    ]

    # Also include items without published_at (might be recent)
    no_time_items = [item for item in unique_items if not item.published_at]

    print(f"Within {hours}h: {len(recent_items)} items")
    print(f"No timestamp: {len(no_time_items)} items (will include)")

    items_to_store = recent_items + no_time_items
    skipped_count = len(unique_items) - len(items_to_store)
    print(f"Skipped (old): {skipped_count} items")

    # Store in database
    print()
    print("Storing in database...")
    stored_count = 0

    async with async_session() as session:
        for item in items_to_store:
            # Find source ID
            source_result = await session.execute(
                select(Source.id).where(Source.name == item.source_name)
            )
            source_row = source_result.first()
            source_id_val = source_row[0] if source_row else None

            raw_item = RawItem(
                source_id=source_id_val,
                title=item.title,
                content=item.content,
                url=item.url,
                author=item.author,
                published_at=item.published_at,
                status="pending",
            )
            session.add(raw_item)
            stored_count += 1

        # Update source last_fetched_at
        for source in sources:
            source.last_fetched_at = datetime.utcnow()
            session.add(source)

        await session.commit()

    # Summary
    print()
    print("=" * 60)
    print("Collection Summary")
    print("=" * 60)
    print(f"Total fetched:     {len(all_items)}")
    print(f"After dedup:       {len(unique_items)}")
    print(f"Skipped (old):     {skipped_count}")
    print(f"Stored:            {stored_count}")
    print(f"Sources ok:        {success_count}")
    print(f"Sources failed:    {fail_count}")
    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {
        "stored": stored_count,
        "skipped": skipped_count,
        "sources_ok": success_count,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run RSS collection")
    parser.add_argument("--source-id", type=int, help="Specific source ID to collect")
    parser.add_argument("--hours", type=int, default=48, help="Time range (hours)")

    args = parser.parse_args()

    asyncio.run(run_collectors(
        source_id=args.source_id,
        hours=args.hours,
    ))
