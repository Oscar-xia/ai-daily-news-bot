#!/usr/bin/env python3
"""
Database initialization script.
Creates all tables and inserts default data.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import engine, async_session, init_db, Base
from app.models.schemas import Source


# Default RSS sources
DEFAULT_RSS_SOURCES = [
    # AI 官方博客
    {"name": "OpenAI Blog", "type": "rss", "url": "https://openai.com/blog/rss.xml", "config": '{"category": "ai"}'},
    {"name": "Anthropic Blog", "type": "rss", "url": "https://www.anthropic.com/news/rss", "config": '{"category": "ai"}'},
    {"name": "Google AI Blog", "type": "rss", "url": "https://blog.google/technology/ai/rss/", "config": '{"category": "ai"}'},
    {"name": "Hugging Face Blog", "type": "rss", "url": "https://huggingface.co/blog/feed.xml", "config": '{"category": "ai"}'},

    # AI 社区
    {"name": "Hacker News AI", "type": "rss", "url": "https://hnrss.org/newest?q=AI&points=50", "config": '{"category": "ai"}'},
    {"name": "Reddit MachineLearning", "type": "rss", "url": "https://www.reddit.com/r/MachineLearning/new/.rss", "config": '{"category": "ai"}'},

    # 投资媒体
    {"name": "a16z Blog", "type": "rss", "url": "https://a16z.com/feed/", "config": '{"category": "investment"}'},
    {"name": "TechCrunch", "type": "rss", "url": "https://techcrunch.com/feed/", "config": '{"category": "investment"}'},
    {"name": "VentureBeat AI", "type": "rss", "url": "https://venturebeat.com/category/ai/feed/", "config": '{"category": "investment"}'},

    # Web3 媒体
    {"name": "The Block", "type": "rss", "url": "https://www.theblock.co/rss.xml", "config": '{"category": "web3"}'},
    {"name": "Bankless", "type": "rss", "url": "https://bankless.substack.com/feed", "config": '{"category": "web3"}'},
    {"name": "Week in Ethereum", "type": "rss", "url": "https://weekinethereumnews.com/feed/", "config": '{"category": "web3"}'},
]


async def create_tables():
    """Create all database tables."""
    print("Creating database tables...")
    await init_db()
    print("✓ Tables created successfully")


async def insert_default_sources():
    """Insert default RSS sources."""
    print("Inserting default RSS sources...")

    async with async_session() as session:
        # Check if sources already exist
        result = await session.execute(select(Source))
        existing = result.scalars().first()

        if existing:
            print("  Sources already exist, skipping...")
            return

        # Insert default sources
        for source_data in DEFAULT_RSS_SOURCES:
            source = Source(**source_data)
            session.add(source)

        await session.commit()
        print(f"✓ Inserted {len(DEFAULT_RSS_SOURCES)} default sources")


async def main():
    """Main initialization function."""
    print("=" * 50)
    print("AI Daily News Bot - Database Initialization")
    print("=" * 50)
    print()

    # Create tables
    await create_tables()

    # Insert default data
    await insert_default_sources()

    print()
    print("=" * 50)
    print("✓ Database initialization complete!")
    print(f"  Database: data/news.db")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
