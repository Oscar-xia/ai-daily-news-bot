"""
Base collector module for AI Daily News Bot.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime


class CollectedItem:
    """Represents a collected news item."""

    def __init__(
        self,
        title: str,
        url: Optional[str] = None,
        content: Optional[str] = None,
        author: Optional[str] = None,
        published_at: Optional[datetime] = None,
        source_name: Optional[str] = None,
        source_type: Optional[str] = None,
        category: Optional[str] = None,
    ):
        self.title = title
        self.url = url
        self.content = content
        self.author = author
        self.published_at = published_at
        self.source_name = source_name
        self.source_type = source_type
        self.category = category

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "url": self.url,
            "content": self.content,
            "author": self.author,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "source_name": self.source_name,
            "source_type": self.source_type,
            "category": self.category,
        }

    def __repr__(self) -> str:
        return f"CollectedItem(title={self.title[:50]}...)"


class BaseCollector(ABC):
    """Abstract base class for collectors."""

    def __init__(self, source_type: str):
        self.source_type = source_type

    @abstractmethod
    async def collect(self, source_config: dict) -> List[CollectedItem]:
        """Collect items from a source.

        Args:
            source_config: Source configuration dict with url, name, etc.

        Returns:
            List of collected items
        """
        pass

    @property
    @abstractmethod
    def source_type_name(self) -> str:
        """Return the source type name."""
        pass
