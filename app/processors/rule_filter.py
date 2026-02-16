"""
Rule-based filter for AI Daily News Bot.
Fast pre-filtering before AI processing.
"""

import re
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from dataclasses import dataclass

from app.config import settings


@dataclass
class FilterResult:
    """Result of rule-based filtering."""
    passed: bool
    reason: Optional[str] = None


# Blacklist keywords for title filtering
TITLE_BLACKLIST = [
    # English
    r"\b[Ss]ponsor(ed)?\b",
    r"\b[Aa][Dd](vertisement)?\b",
    r"\b[Pp]romoted\b",
    r"\b[Hh]ow\s+to\b",
    r"\b[Tt]utorial\b",
    r"\b[Gg]uide\b",
    r"\b[Jj]obs?\b",
    r"\b[Hh]iring\b",
    r"\b[Cc]areer\b",
    r"\b[Ww]eekly\s+[Rr]oundup\b",
    r"\b[Nn]ewsletter\b",
    r"\b[Pp]odcast\b",
    r"\b[Ee]pisode\b",
    r"\b[Rr]ecap\b",
    # Chinese
    r"招聘",
    r"求职",
    r"广告",
    r"教程",
    r"指南",
    r"入门",
    r"周报",
    r"月报",
    r"总结",
    r"盘点",
    r"合辑",
]

# Whitelist keywords (always pass if in title)
TITLE_WHITELIST = [
    # Major AI companies
    r"\bOpenAI\b",
    r"\bAnthropic\b",
    r"\bGoogle\b",
    r"\bDeepMind\b",
    r"\bMeta\b",
    r"\bMicrosoft\b",
    r"\bApple\b",
    r"\bNVIDIA\b",
    r"\bTesla\b",
    # Major crypto
    r"\bEthereum\b",
    r"\bBitcoin\b",
    r"\bSolana\b",
    # Major events
    r"\brelease\b",
    r"\blaunch\b",
    r"\bannounce\b",
    r"\bacquire\b",
    r"\bfunding\b",
    r"\binvest\b",
    r"\bmerger\b",
    # Chinese
    r"发布",
    r"推出",
    r"收购",
    r"融资",
    r"投资",
]


class RuleFilter:
    """Rule-based filter for fast pre-filtering."""

    def __init__(
        self,
        max_age_hours: int = None,
        title_min_length: int = None,
        content_min_length: int = None,
    ):
        self.max_age_hours = max_age_hours or settings.filter_max_age_hours
        self.title_min_length = title_min_length or settings.filter_title_min_length
        self.content_min_length = content_min_length or settings.filter_content_min_length

        # Compile regex patterns
        self.blacklist_patterns = [re.compile(p) for p in TITLE_BLACKLIST]
        self.whitelist_patterns = [re.compile(p) for p in TITLE_WHITELIST]

    def filter(self, title: str, content: str = "", published_at: datetime = None) -> FilterResult:
        """Apply rule-based filters to an item.

        Args:
            title: Item title
            content: Item content (optional)
            published_at: Publication time (optional)

        Returns:
            FilterResult with passed status and reason
        """
        # Check title length
        if len(title) < self.title_min_length:
            return FilterResult(passed=False, reason=f"标题太短 ({len(title)} < {self.title_min_length})")

        # Check content length if provided
        if content and len(content) < self.content_min_length:
            return FilterResult(passed=False, reason=f"内容太短 ({len(content)} < {self.content_min_length})")

        # Check age if published_at provided
        if published_at:
            age = datetime.now(published_at.tzinfo) - published_at if published_at.tzinfo else datetime.utcnow() - published_at
            if age > timedelta(hours=self.max_age_hours):
                return FilterResult(passed=False, reason=f"内容过期 ({age.total_seconds() / 3600:.1f}h > {self.max_age_hours}h)")

        # Check whitelist (always pass)
        for pattern in self.whitelist_patterns:
            if pattern.search(title):
                return FilterResult(passed=True, reason="命中白名单关键词")

        # Check blacklist
        for pattern in self.blacklist_patterns:
            if pattern.search(title):
                return FilterResult(passed=False, reason=f"命中黑名单关键词")

        return FilterResult(passed=True, reason="通过规则过滤")

    def filter_batch(
        self,
        items: List[dict],
        title_key: str = "title",
        content_key: str = "content",
        published_key: str = "published_at"
    ) -> Tuple[List[dict], List[Tuple[dict, str]]]:
        """Filter a batch of items.

        Args:
            items: List of item dictionaries
            title_key: Key for title in dict
            content_key: Key for content in dict
            published_key: Key for published_at in dict

        Returns:
            Tuple of (passed_items, rejected_items_with_reasons)
        """
        passed = []
        rejected = []

        for item in items:
            title = item.get(title_key, "")
            content = item.get(content_key, "")
            published_at = item.get(published_key)

            result = self.filter(title, content, published_at)

            if result.passed:
                passed.append(item)
            else:
                rejected.append((item, result.reason))

        return passed, rejected


def get_rule_filter() -> RuleFilter:
    """Get a configured rule filter instance."""
    return RuleFilter()
