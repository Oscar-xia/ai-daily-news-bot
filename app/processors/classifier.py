"""
Classifier module for AI Daily News Bot.
Extracts keywords and classifies news items using LLM.
"""

from typing import List, Optional, Tuple
import asyncio

from app.collectors.base import CollectedItem
from app.models.schemas import RawItem
from app.llm.base import simple_chat
from app.llm.prompts import (
    get_keywords_prompt,
    parse_keywords_response,
    SYSTEM_PROMPT_KEYWORDS,
)


# Category mapping keywords
CATEGORY_KEYWORDS = {
    "ai": [
        "ai", "artificial intelligence", "machine learning", "deep learning",
        "llm", "gpt", "chatgpt", "claude", "gemini", "openai", "anthropic",
        "neural network", "nlp", "computer vision", "transformer",
        "人工智能", "机器学习", "深度学习", "大模型",
    ],
    "investment": [
        "funding", "investment", "vc", "venture capital", "series a", "series b",
        "ipo", "startup", "unicorn", "valuation", "acquisition", "merger",
        "融资", "投资", "估值", "收购",
    ],
    "web3": [
        "web3", "blockchain", "crypto", "bitcoin", "ethereum", "defi", "nft",
        "smart contract", "dao", "wallet", "token", "coin",
        "区块链", "加密货币", "比特币", "以太坊",
    ],
}


class Classifier:
    """Extracts keywords and classifies news items."""

    def __init__(self, concurrency: int = 5):
        self.concurrency = concurrency

    async def extract_keywords(
        self,
        title: str,
        content: Optional[str] = None
    ) -> List[str]:
        """Extract keywords from a news item.

        Args:
            title: News title
            content: News content (optional)

        Returns:
            List of keywords
        """
        prompt = get_keywords_prompt(title, content or "")

        try:
            response = await simple_chat(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_KEYWORDS,
                temperature=0.3,
                max_tokens=100,
            )

            return parse_keywords_response(response)

        except Exception as e:
            print(f"Error extracting keywords from '{title[:30]}...': {e}")
            return []

    def classify_by_keywords(
        self,
        title: str,
        content: Optional[str] = None,
        keywords: Optional[List[str]] = None
    ) -> str:
        """Classify news item by keywords.

        Args:
            title: News title
            content: News content (optional)
            keywords: Extracted keywords (optional)

        Returns:
            Category: 'ai', 'investment', 'web3', or 'mixed'
        """
        # Combine title, content, and keywords for classification
        text = title.lower()
        if content:
            text += " " + content[:500].lower()
        if keywords:
            text += " " + " ".join(k.lower() for k in keywords)

        # Count matches for each category
        scores = {}
        for category, cat_keywords in CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in cat_keywords if kw in text)
            scores[category] = score

        # Find best category
        max_score = max(scores.values())
        if max_score == 0:
            return "mixed"  # No clear category

        # Check if there's a tie
        best_categories = [cat for cat, score in scores.items() if score == max_score]
        if len(best_categories) > 1:
            return "mixed"

        return best_categories[0]

    async def classify_item(
        self,
        item: CollectedItem
    ) -> Tuple[List[str], str]:
        """Extract keywords and classify an item.

        Args:
            item: CollectedItem to process

        Returns:
            Tuple of (keywords, category)
        """
        keywords = await self.extract_keywords(item.title, item.content)
        category = self.classify_by_keywords(
            item.title,
            item.content,
            keywords
        )

        # Use item's category if available and more specific
        if item.category and item.category != "mixed":
            category = item.category

        return keywords, category

    async def classify_items(
        self,
        items: List[CollectedItem],
        concurrency: Optional[int] = None
    ) -> List[Tuple[List[str], str]]:
        """Classify multiple items.

        Args:
            items: List of items to classify
            concurrency: Max concurrent LLM calls

        Returns:
            List of (keywords, category) tuples
        """
        concurrency = concurrency or self.concurrency
        semaphore = asyncio.Semaphore(concurrency)

        async def classify_with_semaphore(item: CollectedItem):
            async with semaphore:
                return await self.classify_item(item)

        tasks = [classify_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        classified = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"Error classifying item {i}: {result}")
                classified.append(([], "mixed"))
            else:
                classified.append(result)

        return classified
