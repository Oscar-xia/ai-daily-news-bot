"""
Summarizer module for AI Daily News Bot.
Generates summaries using LLM.
"""

from typing import List, Optional
import asyncio

from app.collectors.base import CollectedItem
from app.models.schemas import RawItem
from app.llm.base import simple_chat
from app.llm.prompts import (
    get_summary_prompt,
    SYSTEM_PROMPT_SUMMARY,
)


class Summarizer:
    """Generates summaries using LLM."""

    def __init__(self, concurrency: int = 5):
        self.concurrency = concurrency

    async def summarize(
        self,
        title: str,
        content: Optional[str] = None,
        max_length: int = 100
    ) -> str:
        """Generate a summary for a news item.

        Args:
            title: News title
            content: News content (optional)
            max_length: Maximum summary length in characters

        Returns:
            Generated summary
        """
        prompt = get_summary_prompt(title, content or "")

        try:
            response = await simple_chat(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_SUMMARY,
                temperature=0.3,
                max_tokens=150,
            )

            # Truncate if needed
            summary = response.strip()
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."

            return summary

        except Exception as e:
            print(f"Error summarizing '{title[:30]}...': {e}")
            return ""

    async def summarize_item(self, item: CollectedItem) -> str:
        """Generate summary for a CollectedItem.

        Args:
            item: CollectedItem to summarize

        Returns:
            Generated summary
        """
        return await self.summarize(item.title, item.content)

    async def summarize_items(
        self,
        items: List[CollectedItem],
        concurrency: Optional[int] = None
    ) -> List[str]:
        """Summarize multiple items.

        Args:
            items: List of items to summarize
            concurrency: Max concurrent LLM calls

        Returns:
            List of summaries (same order as input)
        """
        concurrency = concurrency or self.concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def summarize_with_semaphore(item: CollectedItem):
            async with semaphore:
                return await self.summarize_item(item)

        tasks = [summarize_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        summaries = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error summarizing item {i}: {result}")
                summaries.append("")
            else:
                summaries.append(result)

        return summaries
