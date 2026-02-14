"""
AI filter module for AI Daily News Bot.
Filters news items based on relevance using LLM.
"""

from typing import List, Tuple, Optional
import asyncio

from app.collectors.base import CollectedItem
from app.models.schemas import RawItem
from app.llm.base import simple_chat
from app.llm.prompts import (
    get_filter_prompt,
    parse_filter_response,
    SYSTEM_PROMPT_FILTER,
)


class AIFilter:
    """Filters news items using LLM."""

    def __init__(self, concurrency: int = 5):
        self.concurrency = concurrency

    async def is_relevant(self, title: str, content: Optional[str] = None) -> bool:
        """Check if a news item is relevant.

        Args:
            title: News title
            content: News content (optional)

        Returns:
            True if relevant, False otherwise
        """
        prompt = get_filter_prompt(title, content or "")

        try:
            response = await simple_chat(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_FILTER,
                temperature=0.1,  # Low temperature for consistent results
                max_tokens=10,
            )
            return parse_filter_response(response)
        except Exception as e:
            print(f"Error filtering '{title[:30]}...': {e}")
            # Default to keeping the item on error
            return True

    async def filter_item(self, item: CollectedItem) -> Tuple[CollectedItem, bool]:
        """Filter a single item.

        Args:
            item: CollectedItem to filter

        Returns:
            Tuple of (item, is_relevant)
        """
        is_relevant = await self.is_relevant(item.title, item.content)
        return item, is_relevant

    async def filter_items(
        self,
        items: List[CollectedItem],
        concurrency: Optional[int] = None
    ) -> Tuple[List[CollectedItem], List[CollectedItem]]:
        """Filter multiple items.

        Args:
            items: List of items to filter
            concurrency: Max concurrent LLM calls (defaults to self.concurrency)

        Returns:
            Tuple of (relevant_items, discarded_items)
        """
        concurrency = concurrency or self.concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def filter_with_semaphore(item: CollectedItem):
            async with semaphore:
                return await self.filter_item(item)

        tasks = [filter_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        relevant_items = []
        discarded_items = []

        for result in results:
            if isinstance(result, Exception):
                print(f"Error in filter: {result}")
                continue

            item, is_relevant = result
            if is_relevant:
                relevant_items.append(item)
            else:
                discarded_items.append(item)

        return relevant_items, discarded_items

    async def filter_raw_items(
        self,
        items: List[RawItem],
        concurrency: Optional[int] = None
    ) -> Tuple[List[RawItem], List[RawItem]]:
        """Filter RawItem objects from database.

        Args:
            items: List of RawItem objects
            concurrency: Max concurrent LLM calls

        Returns:
            Tuple of (relevant_items, discarded_items)
        """
        concurrency = concurrency or self.concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def filter_raw_item(item: RawItem):
            async with semaphore:
                is_relevant = await self.is_relevant(item.title, item.content)
                return item, is_relevant

        tasks = [filter_raw_item(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        relevant_items = []
        discarded_items = []

        for result in results:
            if isinstance(result, Exception):
                print(f"Error in filter: {result}")
                continue

            item, is_relevant = result
            if is_relevant:
                relevant_items.append(item)
            else:
                discarded_items.append(item)

        return relevant_items, discarded_items
