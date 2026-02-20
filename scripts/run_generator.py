#!/usr/bin/env python3
"""
Report Generator Script.
Version 2.0 - 新模板：摘要+趋势+Top3+可视化+分类分组
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import Counter

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.models.schemas import ProcessedItem, RawItem, Report, ReportItem, Source, CATEGORY_META
from app.llm.base import simple_chat
from app.llm.prompts import get_highlights_prompt, get_insights_prompt, parse_insights_response, get_rejected_prompt
from app.config import settings
from app.notification.email_sender import send_report, is_email_configured


def format_time_ago(published_at: datetime) -> str:
    """Format datetime as relative time."""
    if not published_at:
        return ""

    now = datetime.utcnow()
    diff = now - published_at

    if diff.days > 0:
        return f"{diff.days}天前"
    elif diff.seconds >= 3600:
        return f"{diff.seconds // 3600}小时前"
    elif diff.seconds >= 60:
        return f"{diff.seconds // 60}分钟前"
    else:
        return "刚刚"


def generate_mermaid_pie(data: dict) -> str:
    """Generate Mermaid pie chart."""
    if not data:
        return ""

    lines = ['```mermaid', 'pie showData', '    title "文章分类分布"']
    for cat, count in data.items():
        meta = CATEGORY_META.get(cat, {'emoji': '📝', 'label': cat})
        lines.append(f'    "{meta["emoji"]} {meta["label"]}" : {count}')
    lines.append('```')
    return '\n'.join(lines)


def generate_keyword_chart(keywords: list[tuple]) -> str:
    """Generate Mermaid bar chart for keywords."""
    if not keywords:
        return ""

    labels = [k[0] for k in keywords[:5]]
    values = [k[1] for k in keywords[:5]]
    max_val = max(values) if values else 1

    lines = ['```mermaid', 'xychart-beta horizontal', '    title "高频关键词"']
    lines.append(f'    x-axis {json.dumps(labels)}')
    lines.append(f'    y-axis "出现次数" 0 --> {max_val + 1}')
    lines.append(f'    bar {json.dumps(values)}')
    lines.append('```')
    return '\n'.join(lines)


async def generate_highlights(articles: list[dict]) -> str:
    """Generate highlights summary."""
    prompt = get_highlights_prompt(articles)
    try:
        response = await simple_chat(prompt)
        return response.strip()
    except Exception as e:
        print(f"Highlights error: {e}")
        return "今日技术圈动态持续更新中..."


async def generate_insights(articles: list[dict]) -> dict:
    """Generate daily insights (tech trend, deep thought, money shot)."""
    prompt = get_insights_prompt(articles)
    try:
        response = await simple_chat(prompt, max_tokens=1000)
        result = parse_insights_response(response)
        return result
    except Exception as e:
        print(f"Insights error: {e}")
        return {
            'tech_trend': '',
            'deep_thought': '',
            'money_shot': '',
        }


async def generate_rejected_summary(selected: list, rejected: list) -> str:
    """Generate summary for rejected articles."""
    if not rejected:
        return ""

    prompt = get_rejected_prompt(selected, rejected)
    try:
        response = await simple_chat(prompt, max_tokens=500)
        return response.strip()
    except Exception as e:
        print(f"Rejected summary error: {e}")
        return ""


async def run_generator(
    report_date: date = None,
    min_score: int = 20,
    top_n: int = 15,
    output_dir: str = "output/reports",
    send_email: bool = False,
):
    """Generate daily report with new template.

    Args:
        report_date: Date for the report (default: today)
        min_score: Minimum score threshold (3-30)
        top_n: Number of articles to include
        output_dir: Output directory for report files
    """
    if report_date is None:
        report_date = date.today()

    date_str = report_date.strftime("%Y-%m-%d")

    print("=" * 60)
    print("AI Daily News Bot - Report Generator (v2.0)")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Report date: {date_str}")
    print(f"Min score: {min_score}/30")
    print(f"Top N: {top_n}")
    print()

    # Get processed items with raw_item and source preloaded
    # Only include articles published within last 24h to avoid duplicates across days
    cutoff_time = datetime.utcnow() - timedelta(hours=24)

    async with async_session() as session:
        query = (
            select(ProcessedItem)
            .options(
                selectinload(ProcessedItem.raw_item).selectinload(RawItem.source)
            )
            .join(RawItem, ProcessedItem.raw_item_id == RawItem.id)
            .where(ProcessedItem.approved == True)
            .where(ProcessedItem.total_score >= min_score)
            .where(RawItem.published_at >= cutoff_time)  # Only recent articles
            .order_by(ProcessedItem.total_score.desc())
            .limit(top_n * 2)  # Get more for category distribution
        )

        result = await session.execute(query)
        items = result.scalars().all()

    if not items:
        print("No processed items found.")
        return

    print(f"Found {len(items)} approved items")

    # Take top N
    items = items[:top_n]
    print(f"Using top {len(items)} items")

    # Generate highlights
    print()
    print("Generating highlights...")
    articles_for_highlights = [
        {
            'title_zh': item.title_zh or (item.raw_item.title if item.raw_item else ''),
            'title': item.raw_item.title if item.raw_item else '',
            'summary': item.summary,
            'category': item.category,
            'keywords': json.loads(item.keywords) if item.keywords else [],
        }
        for item in items
    ]
    highlights = await generate_highlights(articles_for_highlights)
    print(f"✓ Highlights generated")

    # Generate insights
    print("Generating insights...")
    insights = await generate_insights(articles_for_highlights)
    print(f"✓ Insights generated")

    # Query rejected articles (approved=False) with full info for table
    print("Querying rejected articles...")
    async with async_session() as reject_session:
        rejected_result = await reject_session.execute(
            select(ProcessedItem)
            .options(
                selectinload(ProcessedItem.raw_item).selectinload(RawItem.source)
            )
            .where(ProcessedItem.approved == False)
            .order_by(ProcessedItem.total_score.desc())
            .limit(20)
        )
        rejected_processed = rejected_result.scalars().all()

        rejected_items = []
        for proc in rejected_processed:
            if proc.raw_item:
                # Get keywords for description
                keywords = []
                if proc.keywords:
                    try:
                        keywords = json.loads(proc.keywords)[:3]
                    except:
                        pass

                # Build brief description: category + keywords
                category_label = CATEGORY_META.get(proc.category, {'label': proc.category})['label']
                if keywords:
                    brief = f"{category_label} · {' '.join(keywords)}"
                else:
                    brief = category_label

                rejected_items.append({
                    'title': proc.title_zh or proc.raw_item.title,
                    'original_title': proc.raw_item.title,
                    'url': proc.raw_item.url,
                    'brief': brief,
                    'score': proc.total_score,
                    'category': proc.category,
                })

    print(f"Found {len(rejected_items)} rejected articles")

    # Calculate statistics
    category_counts = Counter(item.category for item in items)
    all_keywords = []
    for item in items:
        if item.keywords:
            try:
                kws = json.loads(item.keywords)
                all_keywords.extend(kws)
            except:
                pass
    keyword_counts = Counter(all_keywords).most_common(10)

    # Build report content
    print()
    print("Building report...")

    # Header
    content = f"""# 📰 AI 技术日报 — {date_str}

> 来自 90 个顶级技术博客，AI 精选 Top {len(items)}

## 📝 摘要

{highlights}

---

## 🏆 今日必读

"""

    # Top 3 with full details
    for i, item in enumerate(items[:3], 1):
        raw = item.raw_item
        emoji = {"1": "🥇", "2": "🥈", "3": "🥉"}[str(i)]
        title = item.title_zh or (raw.title if raw else "无标题")
        original_title = raw.title if raw and raw.title else ""
        source_name = raw.source.name if raw and raw.source else "Unknown"
        url = raw.url if raw else ""
        time_ago = format_time_ago(raw.published_at) if raw else ""
        keywords_str = ""
        if item.keywords:
            try:
                kws = json.loads(item.keywords)
                keywords_str = " · ".join(kws[:4])
            except:
                pass

        content += f"""{emoji} **{title}**

[{original_title}]({url}) — {source_name} · {time_ago} · ⭐ {item.total_score}/30 · {CATEGORY_META.get(item.category, {}).get('emoji', '📝')} {CATEGORY_META.get(item.category, {}).get('label', item.category)}

> {item.summary or '（无摘要）'}

💡 **推荐理由**: {item.reason or '值得一读'}

🏷️ {keywords_str}

---

"""

    # Statistics section - query real data
    async with async_session() as stat_session:
        # Count sources
        sources_result = await stat_session.execute(select(func.count(Source.id)))
        sources_count = sources_result.scalar() or 0

        # Count articles within 24h
        cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_result = await stat_session.execute(
            select(func.count(RawItem.id)).where(RawItem.published_at >= cutoff)
        )
        recent_count = recent_result.scalar() or 0

        # Count processed items that passed threshold
        passed_result = await stat_session.execute(
            select(func.count(ProcessedItem.id)).where(ProcessedItem.total_score >= min_score)
        )
        passed_count = passed_result.scalar() or 0

    # Calculate selection rate
    selection_rate = round(len(items) / recent_count * 100, 1) if recent_count > 0 else 0

    content += f"""## 📊 今日概览

**📅 {date_str}**

| 信息源 | 24h新文 | 精选 |
|:---:|:---:|:---:|
| {sources_count} | {recent_count} | **{len(items)}** |

入选率: **{selection_rate}%** ({len(items)}/{recent_count})

### 分类分布

{generate_mermaid_pie(dict(category_counts))}

### 高频关键词

{generate_keyword_chart(keyword_counts)}

🏷️ **话题标签**: {' · '.join([f'{k}({c})' for k, c in keyword_counts[:8]])}

---

"""

    # Group by category
    by_category = {}
    for item in items:
        cat = item.category
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(item)

    # Category sections (skip top 3)
    for cat in ['ai-ml', 'engineering', 'tools', 'security', 'opinion', 'other']:
        if cat not in by_category:
            continue

        cat_items = by_category[cat]
        # Skip items already in top 3
        cat_items = [item for item in cat_items if items.index(item) >= 3]

        if not cat_items:
            continue

        meta = CATEGORY_META.get(cat, {'emoji': '📝', 'label': cat})

        content += f"""## {meta['emoji']} {meta['label']}

"""

        for item in cat_items:
            raw = item.raw_item
            title = item.title_zh or (raw.title if raw else "无标题")
            original_title = raw.title if raw and raw.title else ""
            source_name = raw.source.name if raw and raw.source else "Unknown"
            url = raw.url if raw else ""
            time_ago = format_time_ago(raw.published_at) if raw else ""
            keywords_str = ""
            if item.keywords:
                try:
                    kws = json.loads(item.keywords)
                    keywords_str = " · ".join(kws[:4])
                except:
                    pass

            content += f"""### {title}

[{original_title}]({url}) — **{source_name}** · {time_ago} · ⭐ {item.total_score}/30

> {item.summary or '（无摘要）'}

🏷️ {keywords_str}

---

"""

    # Rejected articles section (未入选文章表格)
    if rejected_items:
        content += f"""## 📋 本期未入选

以下文章评分未达门槛（<{min_score}/30），但可能对特定读者有价值：

| 标题 | 简介 | 评分 |
|:-----|:-----|:----:|
"""
        for item in rejected_items[:15]:
            title = item['title'][:40] + ('...' if len(item['title']) > 40 else '')
            url = item['url'] or '#'
            brief = item['brief']
            score = item['score']
            content += f"| [{title}]({url}) | {brief} | {score}/30 |\n"

        content += """
---

"""

    # Insights section (今日启示)
    if insights.get('tech_trend') or insights.get('deep_thought') or insights.get('money_shot'):
        content += """## 💡 今日启示

"""
        if insights.get('tech_trend'):
            content += f"""### 🎯 技术风向

{insights['tech_trend']}

"""
        if insights.get('deep_thought'):
            content += f"""### 🤔 深度思考

{insights['deep_thought']}

"""
        if insights.get('money_shot'):
            content += f"""### 💰 变现机会

{insights['money_shot']}

"""
        content += """---

"""

    # Footer
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    content += f"""*生成于 {timestamp} | 扫描 90 源 → 精选 {len(items)} 篇*

*基于 [Hacker News Popularity Contest 2025](https://refactoringenglish.com/tools/hn-popularity/) 信息源*
"""

    # Save to database
    print("Saving to database...")
    async with async_session() as session:
        # Get max version for this date
        version_result = await session.execute(
            select(func.max(Report.version)).where(Report.report_date == report_date)
        )
        max_version = version_result.scalar() or 0
        new_version = max_version + 1

        report = Report(
            report_date=report_date,
            title=f"AI 技术日报 — {date_str}",
            content=content,
            highlights=highlights,
            status="draft",
            version=new_version,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)

        # Add report items
        for i, item in enumerate(items):
            report_item = ReportItem(
                report_id=report.id,
                processed_item_id=item.id,
                order_index=i,
            )
            session.add(report_item)

        await session.commit()

    # Save to file
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp_file = datetime.now().strftime("%H%M%S")
    output_file = output_path / f"{date_str}_{timestamp_file}.md"
    latest_file = output_path / f"{date_str}_latest.md"

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(content)

    with open(latest_file, "w", encoding="utf-8") as f:
        f.write(content)

    # Summary
    print()
    print("=" * 60)
    print("Report Summary")
    print("=" * 60)
    print(f"Report file: {output_file}")
    print(f"Latest file: {latest_file}")
    print(f"Items included: {len(items)}")
    print(f"Report ID: {report.id}")
    print(f"Version: {report.version}")
    print(f"Status: {report.status}")
    print()
    print(f"Category distribution:")
    for cat, count in category_counts.most_common():
        meta = CATEGORY_META.get(cat, {'emoji': '📝', 'label': cat})
        print(f"  {meta['emoji']} {meta['label']}: {count}")
    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Send email if requested
    if send_email:
        print()
        print("Sending report via email...")
        if is_email_configured():
            success = send_report(content, date_str)
            if success:
                print("✓ Email sent successfully")
            else:
                print("✗ Failed to send email")
        else:
            print("✗ Email not configured. Set EMAIL_ENABLED=True and configure SMTP settings.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate daily report")
    parser.add_argument("--date", type=str, help="Report date (YYYY-MM-DD)")
    parser.add_argument("--min-score", type=int, default=20, help="Minimum score (3-30)")
    parser.add_argument("--top-n", type=int, default=15, help="Top N articles")
    parser.add_argument("--output", type=str, default="output/reports", help="Output directory")
    parser.add_argument("--send-email", action="store_true", help="Send report via email")

    args = parser.parse_args()

    report_date = None
    if args.date:
        report_date = datetime.strptime(args.date, "%Y-%m-%d").date()

    asyncio.run(run_generator(
        report_date=report_date,
        min_score=args.min_score,
        top_n=args.top_n,
        output_dir=args.output,
        send_email=args.send_email,
    ))
