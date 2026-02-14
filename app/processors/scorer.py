"""
Scorer module for AI Daily News Bot.
Scores news items using LLM.
"""

from typing import List, Optional
import asyncio

from app.collectors.base import CollectedItem
from app.models.schemas import RawItem
from app.llm.base import simple_chat
from app.llm.prompts import (
    get_score_prompt,
    parse_score_response,
    SYSTEM_PROMPT_SCORE,
)


class Scorer:
    """Scores news items using LLM."""

    def __init__(self, concurrency: int = 5):
        self.concurrency = concurrency

    async def score(
        self,
        title: str,
        content: Optional[str] = None
    ) -> int:
        """Score a news item.

        Args:
            title: News title
            content: News content (optional)

        Returns:
            Score (0-100)
        """
        prompt = get_score_prompt(title, content or "")

        try:
            response = await simple_chat(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_SCORE,
                temperature=0.2,
                max_tokens=20,
            )

            return parse_score_response(response)

        except Exception as e:
            print(f"Error scoring '{title[:30]}...': {e}")
            return 50  # Default score

    async def score_item(self, item: CollectedItem) -> int:
        """Score a CollectedItem.

        Args:
            item: CollectedItem to score

        Returns:
            Score (0-100)
        """
        return await self.score(item.title, item.content)

    async def score_items(
        self,
        items: List[CollectedItem],
        concurrency: Optional[int] = None
    ) -> List[int]:
        """Score multiple items.

        Args:
            items: List of items to score
            concurrency: Max concurrent LLM calls

        Returns:
            List of scores (same order as input)
        """
        concurrency = concurrency or self.concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def score_with_semaphore(item: CollectedItem):
            async with semaphore:
                return await self.score_item(item)

        tasks = [score_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        scores = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error scoring item {i}: {result}")
                scores.append(50)  # Default score
            else:
                scores.append(result)

        return scores

    async def score_and_sort(
        self,
        items: List[CollectedItem],
        min_score: int = 0
    ) -> List[tuple]:
        """Score items and sort by score.

        Args:
            items: List of items to score
            min_score: Minimum score threshold

        Returns:
            List of (item, score) tuples sorted by score descending
        """
        scores = await self.score_items(items)

        scored_items = [
            (item, score)
            for item, score in zip(items, scores)
            if score >= min_score
        ]

        # Sort by score descending
        scored_items.sort(key=lambda x: x[1], reverse=True)

        return scored_items
