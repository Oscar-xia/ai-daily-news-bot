#!/usr/bin/env python3
"""
Processor Script.
Version 2.0 - 三维评分 + 摘要生成
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from app.database import async_session
from app.models.schemas import RawItem, ProcessedItem, Source
from app.llm.base import simple_chat
from app.llm.prompts import (
    get_scoring_prompt,
    get_summary_prompt,
    parse_scoring_response,
    parse_summary_response,
)
from app.config import settings


# 常量
SCORING_BATCH_SIZE = 10  # 每次评分的文章数
MAX_CONCURRENT_LLM = 2   # 最大并发 LLM 调用


async def score_articles(articles: list[dict]) -> list[dict]:
    """Score a batch of articles using 3-dimension scoring.

    Args:
        articles: List of dicts with index, title, description, sourceName

    Returns:
        List of scoring results
    """
    prompt = get_scoring_prompt(articles)

    try:
        response = await simple_chat(prompt)
        results = parse_scoring_response(response)
        return results
    except Exception as e:
        print(f"    Scoring error: {e}")
        return []


async def summarize_article(title: str, content: str, source: str) -> dict:
    """Generate summary for a single article.

    Args:
        title: Article title
        content: Article content
        source: Source name

    Returns:
        Dict with title_zh, summary, reason
    """
    prompt = get_summary_prompt(title, content, source)

    try:
        response = await simple_chat(prompt)
        result = parse_summary_response(response)
        return result
    except Exception as e:
        print(f"    Summary error: {e}")
        return {'title_zh': '', 'summary': '', 'reason': ''}


async def run_processor(
    min_score: int = 20,
    top_n: int = 15,
    hours: int = 48,
):
    """Run the new processing pipeline.

    Args:
        min_score: Minimum total score (3-30) to include
        top_n: Number of top articles to process
        hours: Time range for filtering
    """
    print("=" * 60)
    print("AI Daily News Bot - Processing (v2.0)")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Min score: {min_score}/30")
    print(f"Top N: {top_n}")
    print(f"Time range: {hours}h")
    print()

    # Get pending items within time range (based on published_at, not fetched_at)
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    async with async_session() as session:
        query = (
            select(RawItem)
            .options(selectinload(RawItem.source))
            .where(RawItem.status == "pending")
            .where(RawItem.published_at >= cutoff_time)  # 使用发布时间过滤
            .order_by(RawItem.published_at.desc())
            .limit(200)  # Process up to 200 items
        )

        result = await session.execute(query)
        pending_items = result.scalars().all()

    if not pending_items:
        print("No pending items to process.")
        return 0

    print(f"Found {len(pending_items)} pending items within {hours}h")
    print()

    # Step 1: Time filter (already done in query)
    print("Step 1/3: Time filtering... ✓")
    print(f"  {len(pending_items)} items within last {hours}h")

    # Step 2: Score articles (batch)
    print()
    print("Step 2/3: AI Scoring (3-dimension)...")

    # Prepare articles for scoring
    articles_to_score = []
    for i, item in enumerate(pending_items):
        articles_to_score.append({
            'index': i,
            'title': item.title,
            'description': item.content or '',
            'sourceName': item.source.name if item.source else 'Unknown',
        })

    # Score in batches
    all_scores = {}
    batches = [articles_to_score[i:i + SCORING_BATCH_SIZE]
               for i in range(0, len(articles_to_score), SCORING_BATCH_SIZE)]

    print(f"  Scoring {len(articles_to_score)} items in {len(batches)} batches...")

    for batch_idx, batch in enumerate(batches):
        # Process with limited concurrency
        results = await score_articles(batch)

        for r in results:
            all_scores[r['index']] = r

        print(f"  Batch {batch_idx + 1}/{len(batches)}: {len(results)} scored")

    print(f"  Total scored: {len(all_scores)}")

    # Step 3: Filter by score and get top N
    print()
    print("Step 3/3: Filtering and summarizing...")

    # Calculate total scores and sort
    scored_items = []
    for i, item in enumerate(pending_items):
        score_data = all_scores.get(i, {
            'relevance': 5, 'quality': 5, 'timeliness': 5,
            'category': 'other', 'keywords': []
        })
        total = score_data['relevance'] + score_data['quality'] + score_data['timeliness']

        scored_items.append({
            'item': item,
            'index': i,
            'total_score': total,
            'relevance': score_data['relevance'],
            'quality': score_data['quality'],
            'timeliness': score_data['timeliness'],
            'category': score_data['category'],
            'keywords': score_data['keywords'],
        })

    # Sort by total score and select top N
    # New logic: if articles <= top_n, select all; otherwise select top N by score
    scored_items.sort(key=lambda x: x['total_score'], reverse=True)

    passed_count = len([x for x in scored_items if x['total_score'] >= min_score])

    if len(scored_items) <= top_n:
        # Not enough articles, select all
        top_items = scored_items
        print(f"  Total articles ({len(scored_items)}) <= target ({top_n}), selecting all")
    else:
        # Select top N by score (min_score is reference, not enforced)
        top_items = scored_items[:top_n]
        print(f"  Items with score >= {min_score}: {passed_count}")
        print(f"  Selected top {len(top_items)} for summary")

    # Generate summaries for top items
    processed_count = 0

    async with async_session() as session:
        for i, scored in enumerate(top_items):
            raw_item = scored['item']

            print(f"  [{i+1}/{len(top_items)}] Summarizing: {raw_item.title[:50]}...")

            # Generate summary
            summary_data = await summarize_article(
                raw_item.title,
                raw_item.content or '',
                raw_item.source.name if raw_item.source else '',
            )

            # Create ProcessedItem
            processed = ProcessedItem(
                raw_item_id=raw_item.id,
                relevance=scored['relevance'],
                quality=scored['quality'],
                timeliness=scored['timeliness'],
                total_score=scored['total_score'],
                category=scored['category'],
                keywords=json.dumps(scored['keywords']),
                title_zh=summary_data.get('title_zh', ''),
                summary=summary_data.get('summary', ''),
                reason=summary_data.get('reason', ''),
                approved=True,  # Auto-approve items that pass the threshold
            )
            session.add(processed)

            # Update raw item status
            raw_item.status = "scored"

            processed_count += 1

        # Mark remaining items as scored (but not processed) - create ProcessedItem without summary
        for scored in scored_items:
            if scored not in top_items:
                raw_item = scored['item']
                raw_item.status = "scored"

                # Create ProcessedItem without summary (approved=False)
                processed = ProcessedItem(
                    raw_item_id=raw_item.id,
                    relevance=scored['relevance'],
                    quality=scored['quality'],
                    timeliness=scored['timeliness'],
                    total_score=scored['total_score'],
                    category=scored['category'],
                    keywords=json.dumps(scored['keywords']),
                    title_zh='',  # No Chinese title for rejected items
                    summary='',   # No summary for rejected items
                    reason='',    # No reason for rejected items
                    approved=False,  # Not approved for report
                )
                session.add(processed)

        await session.commit()

    # Summary
    passed_count = len([x for x in scored_items if x['total_score'] >= min_score])

    # Collect rejected articles info for report
    rejected_items = []
    for scored in scored_items:
        if scored not in top_items:
            rejected_items.append({
                'title': scored['item'].title,
                'score': scored['total_score'],
                'category': scored['category'],
            })

    print()
    print("=" * 60)
    print("Processing Summary")
    print("=" * 60)
    print(f"Total pending:     {len(pending_items)}")
    print(f"Scored:            {len(all_scores)}")
    print(f"Score >= {min_score}:    {passed_count}")
    print(f"Summarized:        {processed_count}")
    print(f"Rejected:          {len(rejected_items)}")
    print()
    print(f"Score distribution:")
    for threshold in [25, 22, 20, 18, 15]:
        count = len([x for x in scored_items if x['total_score'] >= threshold])
        print(f"  >= {threshold}: {count} items")
    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return {
        "total": len(pending_items),
        "scored": len(all_scores),
        "passed": passed_count,
        "summarized": processed_count,
        "min_score": min_score,
        "rejected": rejected_items,  # 被淘汰的文章
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run AI processing")
    parser.add_argument("--min-score", type=int, default=15, help="Minimum score (3-30, soft threshold)")
    parser.add_argument("--top-n", type=int, default=15, help="Top N articles to summarize")
    parser.add_argument("--hours", type=int, default=24, help="Time range (hours)")

    args = parser.parse_args()

    asyncio.run(run_processor(
        min_score=args.min_score,
        top_n=args.top_n,
        hours=args.hours,
    ))
