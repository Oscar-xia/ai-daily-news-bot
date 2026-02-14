#!/usr/bin/env python3
"""
Run processor script.
Process pending raw items through AI pipeline.
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from app.database import async_session
from app.models.schemas import RawItem, ProcessedItem
from app.processors.deduplicator import Deduplicator
from app.processors.filter import AIFilter
from app.processors.summarizer import Summarizer
from app.processors.classifier import Classifier
from app.processors.scorer import Scorer


async def process_item(
    raw_item: RawItem,
    filter_: AIFilter,
    summarizer: Summarizer,
    classifier: Classifier,
    scorer: Scorer,
) -> Optional[ProcessedItem]:
    """Process a single raw item through AI pipeline.

    Returns:
        ProcessedItem if relevant, None if discarded
    """
    # Step 1: Filter for relevance
    is_relevant = await filter_.is_relevant(raw_item.title, raw_item.content)
    if not is_relevant:
        return None

    # Step 2: Generate summary
    summary = await summarizer.summarize(raw_item.title, raw_item.content)

    # Step 3: Extract keywords and classify
    keywords, category = await classifier.classify_item(
        type("Item", (), {"title": raw_item.title, "content": raw_item.content, "category": raw_item.category})()
    )

    # Step 4: Score
    score = await scorer.score(raw_item.title, raw_item.content)

    # Create processed item
    processed = ProcessedItem(
        raw_item_id=raw_item.id,
        summary=summary,
        keywords=json.dumps(keywords) if keywords else None,
        score=score,
        is_duplicate=False,
        approved=False,
    )

    return processed


async def run_processor(
    item_ids: Optional[List[int]] = None,
    min_score_threshold: int = 0,
    limit: int = 50
):
    """Run processor on pending items.

    Args:
        item_ids: Specific item IDs to process (None for all pending)
        min_score_threshold: Minimum score to keep
        limit: Maximum items to process
    """
    print("=" * 60)
    print("AI Daily News Bot - AI Processing")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Initialize processors
    filter_ = AIFilter(concurrency=5)
    summarizer = Summarizer(concurrency=5)
    classifier = Classifier(concurrency=5)
    scorer = Scorer(concurrency=5)

    # Get pending items
    async with async_session() as session:
        query = select(RawItem).where(RawItem.status == "pending")

        if item_ids:
            query = query.where(RawItem.id.in_(item_ids))

        query = query.limit(limit)
        result = await session.execute(query)
        pending_items = result.scalars().all()

    if not pending_items:
        print("No pending items to process.")
        return

    print(f"Found {len(pending_items)} pending items to process.")
    print()

    # Process items
    processed_count = 0
    discarded_count = 0
    error_count = 0

    for i, raw_item in enumerate(pending_items, 1):
        print(f"[{i}/{len(pending_items)}] Processing: {raw_item.title[:50]}...")

        try:
            processed = await process_item(
                raw_item, filter_, summarizer, classifier, scorer
            )

            if processed is None:
                print(f"  Discarded (not relevant)")
                discarded_count += 1
                raw_item.status = "discarded"
            elif processed.score < min_score_threshold:
                print(f"  Discarded (score too low: {processed.score})")
                discarded_count += 1
                raw_item.status = "discarded"
            else:
                print(f"  Processed (score: {processed.score})")
                processed_count += 1
                raw_item.status = "processed"

                # Save processed item
                async with async_session() as session:
                    session.add(processed)
                    session.add(raw_item)
                    await session.commit()

        except Exception as e:
            print(f"  Error: {e}")
            error_count += 1

    # Summary
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Processed: {processed_count}")
    print(f"Discarded: {discarded_count}")
    print(f"Errors: {error_count}")
    print()
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Run AI processor")
    parser.add_argument(
        "--ids", "-i",
        type=int,
        nargs="+",
        help="Specific item IDs to process"
    )
    parser.add_argument(
        "--min-score", "-m",
        type=int,
        default=0,
        help="Minimum score threshold"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        default=50,
        help="Maximum items to process"
    )

    args = parser.parse_args()

    asyncio.run(run_processor(args.ids, args.min_score, args.limit))


if __name__ == "__main__":
    main()
