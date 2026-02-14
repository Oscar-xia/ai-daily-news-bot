"""
RSS collector for AI Daily News Bot.
"""

import feedparser
from typing import List, Optional
from datetime import datetime
import httpx
import asyncio

from app.collectors.base import BaseCollector, CollectedItem


class RSSCollector(BaseCollector):
    """Collector for RSS feeds."""

    def __init__(self):
        super().__init__("rss")
        self.timeout = 30.0

    @property
    def source_type_name(self) -> str:
        return "RSS Feed"

    async def collect(self, source_config: dict) -> List[CollectedItem]:
        """Collect items from an RSS feed.

        Args:
            source_config: Dict with keys:
                - url: RSS feed URL
                - name: Source name
                - config: Optional JSON config with category

        Returns:
            List of collected items
        """
        url = source_config.get("url")
        name = source_config.get("name", "Unknown")

        if not url:
            return []

        # Get category from config
        import json
        category = None
        config_str = source_config.get("config")
        if config_str:
            try:
                config = json.loads(config_str)
                category = config.get("category")
            except json.JSONDecodeError:
                pass

        items = []

        try:
            # Fetch RSS content
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, follow_redirects=True)
                response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            if feed.bozo and feed.bozo_exception:
                # Feed parsing error
                print(f"Warning: RSS parsing issue for {name}: {feed.bozo_exception}")

            for entry in feed.entries:
                item = self._parse_entry(entry, name, category)
                if item:
                    items.append(item)

        except httpx.HTTPError as e:
            print(f"HTTP error fetching {name}: {e}")
        except Exception as e:
            print(f"Error collecting from {name}: {e}")

        return items

    def _parse_entry(
        self,
        entry,
        source_name: str,
        category: Optional[str]
    ) -> Optional[CollectedItem]:
        """Parse an RSS entry into a CollectedItem.

        Args:
            entry: feedparser entry object
            source_name: Name of the source
            category: Optional category override

        Returns:
            CollectedItem or None if invalid
        """
        # Get title
        title = entry.get("title", "")
        if not title:
            return None

        # Get URL
        url = entry.get("link", "")
        if not url:
            # Try alternate link
            links = entry.get("links", [])
            if links:
                url = links[0].get("href", "")

        # Get content
        content = ""
        if "content" in entry:
            content = entry.content[0].get("value", "")
        elif "summary" in entry:
            content = entry.summary
        elif "description" in entry:
            content = entry.description

        # Get author
        author = None
        if "author" in entry:
            author = entry.author
        elif "authors" in entry and entry.authors:
            author = entry.authors[0].get("name")

        # Get published date
        published_at = None
        if "published_parsed" in entry and entry.published_parsed:
            try:
                published_at = datetime(*entry.published_parsed[:6])
            except (ValueError, TypeError):
                pass
        elif "updated_parsed" in entry and entry.updated_parsed:
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
            category=category,
        )

    async def collect_many(
        self,
        sources: List[dict],
        concurrency: int = 5
    ) -> List[CollectedItem]:
        """Collect from multiple RSS sources concurrently.

        Args:
            sources: List of source configs
            concurrency: Max concurrent requests

        Returns:
            List of all collected items
        """
        semaphore = asyncio.Semaphore(concurrency)
        all_items = []

        async def collect_with_semaphore(source):
            async with semaphore:
                return await self.collect(source)

        tasks = [collect_with_semaphore(source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                print(f"Error in concurrent collection: {result}")

        return all_items
