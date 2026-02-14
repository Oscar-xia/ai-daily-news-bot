"""
Report generator for AI Daily News Bot.
Generates Markdown daily reports using LLM.
"""

from typing import List, Optional
from datetime import date, datetime, timedelta
import asyncio

from app.models.schemas import ProcessedItem, Report
from app.llm.base import simple_chat
from app.llm.prompts import (
    get_report_prompt,
    SYSTEM_PROMPT_REPORT,
)


class ReportGenerator:
    """Generates Markdown daily reports."""

    def __init__(self, concurrency: int = 3):
        self.concurrency = concurrency

    def _format_items_for_prompt(self, items: List[ProcessedItem]) -> List[dict]:
        """Format processed items for prompt.

        Args:
            items: List of ProcessedItem objects

        Returns:
            List of formatted item dicts
        """
        formatted = []
        for item in items:
            formatted.append({
                "title": item.raw_item.title if item.raw_item else "",
                "summary": item.summary or "",
                "url": item.raw_item.url if item.raw_item else "",
                "category": item.raw_item.category if item.raw_item else "mixed",
                "score": item.score,
            })
        return formatted

    async def generate(
        self,
        items: List[ProcessedItem],
        report_date: Optional[date] = None
    ) -> str:
        """Generate a daily report.

        Args:
            items: List of ProcessedItem objects to include
            report_date: Date for the report (defaults to today)

        Returns:
            Markdown formatted report
        """
        report_date = report_date or date.today()
        date_str = report_date.strftime("%Y-%m-%d")

        if not items:
            return self._generate_empty_report(date_str)

        # Sort items by score
        sorted_items = sorted(items, key=lambda x: x.score, reverse=True)

        # Format items for prompt
        formatted_items = self._format_items_for_prompt(sorted_items)

        # Generate prompt
        prompt = get_report_prompt(formatted_items, date_str)

        try:
            response = await simple_chat(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT_REPORT,
                temperature=0.5,
                max_tokens=4000,
            )

            return response.strip()

        except Exception as e:
            print(f"Error generating report: {e}")
            return self._generate_fallback_report(sorted_items, date_str)

    def _generate_empty_report(self, date_str: str) -> str:
        """Generate an empty report.

        Args:
            date_str: Date string

        Returns:
            Empty report markdown
        """
        return f"""# AI Daily News - {date_str}

今日暂无重要新闻。

---

*生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

    def _generate_fallback_report(
        self,
        items: List[ProcessedItem],
        date_str: str
    ) -> str:
        """Generate a fallback report without LLM.

        Args:
            items: List of ProcessedItem objects
            date_str: Date string

        Returns:
            Fallback report markdown
        """
        # Group by category
        ai_items = []
        investment_items = []
        web3_items = []
        mixed_items = []

        for item in items:
            category = item.raw_item.category if item.raw_item else "mixed"
            if category == "ai":
                ai_items.append(item)
            elif category == "investment":
                investment_items.append(item)
            elif category == "web3":
                web3_items.append(item)
            else:
                mixed_items.append(item)

        def format_section(section_items: List[ProcessedItem]) -> str:
            if not section_items:
                return "暂无内容\n"

            lines = []
            for i, item in enumerate(section_items, 1):
                title = item.raw_item.title if item.raw_item else "无标题"
                summary = item.summary or "无摘要"
                url = item.raw_item.url if item.raw_item else ""

                lines.append(f"### {i}. {title}")
                lines.append("")
                lines.append(summary)
                if url:
                    lines.append("")
                    lines.append(f"[来源]({url})")
                lines.append("")
                lines.append("---")
                lines.append("")

            return "\n".join(lines)

        report = f"""# AI Daily News - {date_str}

## 目录

- [AI 技术](#ai-技术)
- [AI 投资](#ai-投资)
- [Web3](#web3)

---

## AI 技术

{format_section(ai_items)}

## AI 投资

{format_section(investment_items)}

## Web3

{format_section(web3_items)}

---

*生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*
"""

        return report

    def generate_report_object(
        self,
        items: List[ProcessedItem],
        report_date: Optional[date] = None
    ) -> Report:
        """Generate a Report object.

        Args:
            items: List of ProcessedItem objects
            report_date: Date for the report

        Returns:
            Report object
        """
        report_date = report_date or date.today()

        return Report(
            report_date=report_date,
            title=f"AI Daily News - {report_date.strftime('%Y-%m-%d')}",
            content="",  # Will be filled by generate()
            status="draft",
        )
