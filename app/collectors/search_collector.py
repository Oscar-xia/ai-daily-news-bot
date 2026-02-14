"""
AI Search collector for AI Daily News Bot.
Uses Tavily API for AI-powered search.
"""

from typing import List, Optional
from datetime import datetime
import httpx
import asyncio
import json

from app.collectors.base import BaseCollector, CollectedItem
from app.config import settings


# Default search queries
DEFAULT_SEARCH_QUERIES = [
    "AI news today",
    "artificial intelligence breakthrough",
    "Web3 news",
    "crypto news",
    "VC funding AI startup",
    "LLM news",
]


class SearchCollector(BaseCollector):
    """Collector using Tavily AI Search API."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("search")
        self.api_key = api_key or settings.tavily_api_key
        self.base_url = "https://api.tavily.com"
        self.timeout = 30.0

    @property
    def source_type_name(self) -> str:
        return "AI Search (Tavily)"

    async def collect(self, source_config: dict) -> List[CollectedItem]:
        """Collect items using Tavily search.

        Args:
            source_config: Dict with keys:
                - url: Search query (or use 'query' key)
                - name: Source name
                - config: Optional JSON config with category

        Returns:
            List of collected items
        """
        query = source_config.get("url") or source_config.get("query", "")
        name = source_config.get("name", f"Search: {query[:30]}")

        if not query:
            return []

        # Parse config for category
        category = None
        config_str = source_config.get("config")
        if config_str:
            try:
                config = json.loads(config_str)
                category = config.get("category")
            except json.JSONDecodeError:
                pass

        if not self.api_key:
            print("Warning: TAVILY_API_KEY not configured")
            return []

        items = []

        try:
            results = await self._search(query)

            for result in results:
                item = self._parse_result(result, name, category)
                if item:
                    items.append(item)

        except Exception as e:
            print(f"Error searching '{query}': {e}")

        return items

    async def _search(self, query: str, max_results: int = 10) -> List[dict]:
        """Perform search using Tavily API.

        Args:
            query: Search query
            max_results: Maximum number of results

        Returns:
            List of search results
        """
        url = f"{self.base_url}/search"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "query": query,
            "max_results": max_results,
            "include_raw_content": False,
            "include_answer": False,
            "search_depth": "basic",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()

            data = response.json()
            return data.get("results", [])

    def _parse_result(
        self,
        result: dict,
        source_name: str,
        category: Optional[str]
    ) -> Optional[CollectedItem]:
        """Parse a Tavily search result into a CollectedItem.

        Args:
            result: Tavily result dict
            source_name: Name of the source
            category: Optional category override

        Returns:
            CollectedItem or None if invalid
        """
        title = result.get("title", "")
        if not title:
            return None

        url = result.get("url", "")
        content = result.get("content", "") or result.get("raw_content", "")
        published_at = None

        # Try to parse publish date if available
        if "published_date" in result:
            try:
                published_at = datetime.fromisoformat(result["published_date"].replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        return CollectedItem(
            title=title,
            url=url,
            content=content,
            author=None,
            published_at=published_at,
            source_name=source_name,
            source_type="search",
            category=category,
        )

    async def search(
        self,
        query: str,
        max_results: int = 10
    ) -> List[CollectedItem]:
        """Convenience method for single search.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of collected items
        """
        source_config = {
            "query": query,
            "name": f"Search: {query[:30]}",
        }
        return await self.collect(source_config)

    async def search_multiple(
        self,
        queries: List[str],
        concurrency: int = 3
    ) -> List[CollectedItem]:
        """Search multiple queries concurrently.

        Args:
            queries: List of search queries
            concurrency: Max concurrent requests

        Returns:
            List of all collected items
        """
        semaphore = asyncio.Semaphore(concurrency)
        all_items = []

        async def search_with_semaphore(query: str):
            async with semaphore:
                return await self.search(query)

        tasks = [search_with_semaphore(query) for query in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_items.extend(result)
            elif isinstance(result, Exception):
                print(f"Error in search: {result}")

        return all_items

    async def collect_default_queries(self) -> List[CollectedItem]:
        """Collect using default search queries.

        Returns:
            List of collected items
        """
        return await self.search_multiple(DEFAULT_SEARCH_QUERIES)
