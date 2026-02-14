"""
Deduplication module for AI Daily News Bot.
Handles URL and title similarity deduplication.
"""

from typing import List, Optional, Set, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import re

from app.collectors.base import CollectedItem
from app.models.schemas import RawItem


@dataclass
class DeduplicationResult:
    """Result of deduplication check."""
    is_duplicate: bool
    reason: Optional[str] = None
    similar_to: Optional[str] = None  # URL or title of existing item


class Deduplicator:
    """Handles deduplication of news items."""

    def __init__(
        self,
        url_similarity_threshold: float = 1.0,
        title_similarity_threshold: float = 0.85,
    ):
        self.url_similarity_threshold = url_similarity_threshold
        self.title_similarity_threshold = title_similarity_threshold
        self._seen_urls: Set[str] = set()
        self._seen_titles: Set[str] = set()
        self._url_hash_map: dict = {}  # hash -> original URL
        self._title_hash_map: dict = {}  # normalized title -> original title

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison.

        Args:
            url: Original URL

        Returns:
            Normalized URL
        """
        if not url:
            return ""

        # Remove protocol
        url = re.sub(r'^https?://', '', url.lower())
        # Remove www
        url = re.sub(r'^www\.', '', url)
        # Remove trailing slash
        url = url.rstrip('/')
        # Remove common tracking parameters
        url = re.sub(r'[?&](utm_\w+|ref|source|campaign)=[^&]*', '', url)
        url = re.sub(r'\?$', '', url)

        return url

    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison.

        Args:
            title: Original title

        Returns:
            Normalized title
        """
        if not title:
            return ""

        # Lowercase
        title = title.lower()
        # Remove extra whitespace
        title = ' '.join(title.split())
        # Remove common prefixes/suffixes
        title = re.sub(r'^(breaking:?\s*|just in:?\s*|update:?\s*)', '', title)
        title = re.sub(r'\s*-\s*[^-]+$', '', title)  # Remove trailing "- Source"

        return title

    def _get_url_hash(self, url: str) -> str:
        """Get hash of normalized URL.

        Args:
            url: URL to hash

        Returns:
            Hash string
        """
        normalized = self._normalize_url(url)
        return hashlib.md5(normalized.encode()).hexdigest()

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity ratio between two texts.

        Args:
            text1: First text
            text2: Second text

        Returns:
            Similarity ratio (0-1)
        """
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1, text2).ratio()

    def check_url_duplicate(self, url: str) -> DeduplicationResult:
        """Check if URL is a duplicate.

        Args:
            url: URL to check

        Returns:
            DeduplicationResult
        """
        if not url:
            return DeduplicationResult(is_duplicate=False)

        normalized = self._normalize_url(url)
        url_hash = self._get_url_hash(url)

        if url_hash in self._seen_urls:
            return DeduplicationResult(
                is_duplicate=True,
                reason="URL already seen",
                similar_to=self._url_hash_map.get(url_hash)
            )

        return DeduplicationResult(is_duplicate=False)

    def check_title_duplicate(self, title: str) -> DeduplicationResult:
        """Check if title is a duplicate.

        Args:
            title: Title to check

        Returns:
            DeduplicationResult
        """
        if not title:
            return DeduplicationResult(is_duplicate=False)

        normalized = self._normalize_title(title)

        # Check exact match first
        if normalized in self._seen_titles:
            return DeduplicationResult(
                is_duplicate=True,
                reason="Title already seen (exact match)",
                similar_to=self._title_hash_map.get(normalized)
            )

        # Check similar titles
        for seen_title in self._seen_titles:
            similarity = self._calculate_similarity(normalized, seen_title)
            if similarity >= self.title_similarity_threshold:
                return DeduplicationResult(
                    is_duplicate=True,
                    reason=f"Similar title (similarity: {similarity:.2f})",
                    similar_to=self._title_hash_map.get(seen_title)
                )

        return DeduplicationResult(is_duplicate=False)

    def check_duplicate(self, item: CollectedItem) -> DeduplicationResult:
        """Check if item is a duplicate.

        Args:
            item: CollectedItem to check

        Returns:
            DeduplicationResult
        """
        # Check URL first (higher priority)
        if item.url:
            url_result = self.check_url_duplicate(item.url)
            if url_result.is_duplicate:
                return url_result

        # Then check title
        return self.check_title_duplicate(item.title)

    def add_item(self, item: CollectedItem) -> None:
        """Add item to seen items.

        Args:
            item: CollectedItem to add
        """
        if item.url:
            url_hash = self._get_url_hash(item.url)
            self._seen_urls.add(url_hash)
            self._url_hash_map[url_hash] = item.url

        normalized_title = self._normalize_title(item.title)
        if normalized_title:
            self._seen_titles.add(normalized_title)
            self._title_hash_map[normalized_title] = item.title

    def add_existing_items(self, items: List[RawItem]) -> None:
        """Add existing items from database to seen items.

        Args:
            items: List of existing RawItem objects
        """
        for item in items:
            if item.url:
                url_hash = self._get_url_hash(item.url)
                self._seen_urls.add(url_hash)
                self._url_hash_map[url_hash] = item.url

            normalized_title = self._normalize_title(item.title)
            if normalized_title:
                self._seen_titles.add(normalized_title)
                self._title_hash_map[normalized_title] = item.title

    def deduplicate(
        self,
        new_items: List[CollectedItem],
        existing_items: Optional[List[RawItem]] = None
    ) -> Tuple[List[CollectedItem], List[Tuple[CollectedItem, str]]]:
        """Deduplicate a list of new items.

        Args:
            new_items: List of new items to deduplicate
            existing_items: Optional list of existing items to compare against

        Returns:
            Tuple of (unique_items, duplicate_items_with_reasons)
        """
        # Reset and add existing items
        self._seen_urls.clear()
        self._seen_titles.clear()
        self._url_hash_map.clear()
        self._title_hash_map.clear()

        if existing_items:
            self.add_existing_items(existing_items)

        unique_items = []
        duplicate_items = []

        for item in new_items:
            result = self.check_duplicate(item)

            if result.is_duplicate:
                duplicate_items.append((item, result.reason or "Unknown"))
            else:
                unique_items.append(item)
                self.add_item(item)

        return unique_items, duplicate_items

    def get_stats(self) -> dict:
        """Get deduplication statistics.

        Returns:
            Dict with stats
        """
        return {
            "seen_urls": len(self._seen_urls),
            "seen_titles": len(self._seen_titles),
        }

    def reset(self) -> None:
        """Reset all seen items."""
        self._seen_urls.clear()
        self._seen_titles.clear()
        self._url_hash_map.clear()
        self._title_hash_map.clear()
