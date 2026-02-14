"""
Twitter collector for AI Daily News Bot.
Uses RSSHub to convert Twitter feeds to RSS format.
"""

import feedparser
from typing import List, Optional
from datetime import datetime
import httpx
import asyncio
import json

from app.collectors.base import BaseCollector, CollectedItem
from app.config import settings


class TwitterCollector(BaseCollector):
    """Collector for Twitter via RSSHub."""

    def __init__(self, rsshub_base_url: Optional[str] = None):
        super().__init__("twitter")
        self.rsshub_base_url = (rsshub_base_url or settings.rsshub_base_url).rstrip("/")
        self.timeout = 30.0

    @property
    def source_type_name(self) -> str:
        return "Twitter (RSSHub)"

    def _get_user_rss_url(self, username: str) -> str:
        """Get RSSHub URL for a Twitter user.

        Args:
            username: Twitter username (without @)

        Returns:
            RSSHub RSS URL
        """
        # RSSHub Twitter user endpoint
        return f"{self.rsshub_base_url}/twitter/user/{username}"

    async def collect(self, source_config: dict) -> List[CollectedItem]:
        """Collect items from a Twitter user via RSSHub.

        Args:
            source_config: Dict with keys:
                - url: Twitter username or RSSHub URL
                - name: Source name
                - config: Optional JSON config

        Returns:
            List of collected items
        """
        url = source_config.get("url", "")
        name = source_config.get("name", "Unknown")

        # Parse config for category
        category = None
        config_str = source_config.get("config")
        if config_str:
            try:
                config = json.loads(config_str)
                category = config.get("category")
            except json.JSONDecodeError:
                pass

        # Determine RSS URL
        if url.startswith("http"):
            rss_url = url
        else:
            # Assume it's a username
            username = url.lstrip("@")
            rss_url = self._get_user_rss_url(username)

        items = []

        try:
            # Fetch RSS content
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(rss_url, follow_redirects=True)
                response.raise_for_status()

            # Parse RSS feed
            feed = feedparser.parse(response.content)

            for entry in feed.entries:
                item = self._parse_entry(entry, name, category)
                if item:
                    items.append(item)

        except httpx.HTTPError as e:
            print(f"HTTP error fetching Twitter feed {name}: {e}")
        except Exception as e:
            print(f"Error collecting from {name}: {e}")

        return items

    def _parse_entry(
        self,
        entry,
        source_name: str,
        category: Optional[str]
    ) -> Optional[CollectedItem]:
        """Parse an RSS entry (from RSSHub Twitter feed) into a CollectedItem.

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

        # Get URL - try to extract original Twitter URL
        url = entry.get("link", "")
        if not url:
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

        # Clean content (remove HTML tags if present)
        content = self._clean_html(content)

        # Get author (Twitter username)
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
            source_type="twitter",
            category=category,
        )

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text.

        Args:
            text: Text possibly containing HTML

        Returns:
            Cleaned text
        """
        import re
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode HTML entities
        import html
        text = html.unescape(text)
        return text.strip()

    async def collect_users(
        self,
        usernames: List[str],
        concurrency: int = 3
    ) -> List[CollectedItem]:
        """Collect from multiple Twitter users.

        Args:
            usernames: List of Twitter usernames
            concurrency: Max concurrent requests (keep low to avoid rate limits)

        Returns:
            List of all collected items
        """
        semaphore = asyncio.Semaphore(concurrency)
        all_items = []

        async def collect_user(username: str):
            source_config = {
                "url": username,
                "name": f"@{username}",
                "config": '{"category": "mixed"}'
            }
            async with semaphore:
                await asyncio.sleep(1)  # Rate limiting
                return await self.collect(source_config)

        tasks = [collect_user(username) for username in usernames]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                print(f"Error collecting Twitter user: {result}")

        return all_items

    async def collect_from_config(self) -> List[CollectedItem]:
        """Collect from Twitter users configured in settings.

        Returns:
            List of collected items
        """
        usernames = settings.twitter_user_list
        if not usernames:
            print("No Twitter users configured in TWITTER_USERS")
            return []

        return await self.collect_users(usernames)
