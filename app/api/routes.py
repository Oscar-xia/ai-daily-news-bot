"""
API routes for AI Daily News Bot.
"""

from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.schemas import (
    Source, RawItem, ProcessedItem, Report,
    SourceCreate, SourceResponse,
    RawItemCreate, RawItemResponse,
    ProcessedItemResponse,
    ReportCreate, ReportResponse, ReportGenerateRequest,
    CollectRequest,
)


router = APIRouter()


# =============================================================================
# Sources API
# =============================================================================

@router.get("/sources", response_model=List[SourceResponse])
async def get_sources(
    source_type: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """Get all sources."""
    query = select(Source)

    if source_type:
        query = query.where(Source.type == source_type)

    result = await session.execute(query)
    return result.scalars().all()


@router.post("/sources", response_model=SourceResponse)
async def create_source(
    source: SourceCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new source."""
    db_source = Source(**source.dict())
    session.add(db_source)
    await session.commit()
    await session.refresh(db_source)
    return db_source


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific source."""
    result = await session.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalars().first()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    return source


# =============================================================================
# Raw Items API
# =============================================================================

@router.get("/items", response_model=List[RawItemResponse])
async def get_items(
    status: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """Get raw items."""
    query = select(RawItem)

    if status:
        query = query.where(RawItem.status == status)

    query = query.order_by(RawItem.fetched_at.desc()).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


@router.post("/items", response_model=RawItemResponse)
async def create_item(
    item: RawItemCreate,
    session: AsyncSession = Depends(get_session)
):
    """Manually create a raw item."""
    db_item = RawItem(**item.dict(), status="pending")
    session.add(db_item)
    await session.commit()
    await session.refresh(db_item)
    return db_item


@router.get("/items/{item_id}", response_model=RawItemResponse)
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific raw item."""
    result = await session.execute(
        select(RawItem).where(RawItem.id == item_id)
    )
    item = result.scalars().first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


# =============================================================================
# Processed Items API
# =============================================================================

@router.get("/processed", response_model=List[ProcessedItemResponse])
async def get_processed_items(
    approved: Optional[bool] = None,
    min_score: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """Get processed items."""
    query = select(ProcessedItem)

    if approved is not None:
        query = query.where(ProcessedItem.approved == approved)

    query = query.where(ProcessedItem.score >= min_score)
    query = query.order_by(ProcessedItem.score.desc()).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


@router.post("/processed/{item_id}/approve")
async def approve_item(
    item_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Approve a processed item."""
    result = await session.execute(
        select(ProcessedItem).where(ProcessedItem.id == item_id)
    )
    item = result.scalars().first()

    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    item.approved = True
    await session.commit()

    return {"message": "Item approved", "item_id": item_id}


# =============================================================================
# Reports API
# =============================================================================

@router.get("/reports", response_model=List[ReportResponse])
async def get_reports(
    limit: int = 10,
    session: AsyncSession = Depends(get_session)
):
    """Get all reports."""
    query = select(Report).order_by(Report.report_date.desc()).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/reports/{report_date}", response_model=ReportResponse)
async def get_report(
    report_date: date,
    session: AsyncSession = Depends(get_session)
):
    """Get report by date."""
    result = await session.execute(
        select(Report).where(Report.report_date == report_date)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return report


@router.post("/reports/generate")
async def generate_report(
    request: ReportGenerateRequest = None,
    session: AsyncSession = Depends(get_session)
):
    """Generate a new report."""
    from scripts.run_generator import run_generator

    report_date = request.report_date if request else None

    await run_generator(
        report_date=report_date,
        min_score=request.min_score if request else 50
    )

    return {"message": "Report generated", "date": str(report_date or date.today())}


@router.put("/reports/{report_date}/publish")
async def publish_report(
    report_date: date,
    session: AsyncSession = Depends(get_session)
):
    """Publish a report."""
    result = await session.execute(
        select(Report).where(Report.report_date == report_date)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = "published"
    await session.commit()

    return {"message": "Report published", "date": str(report_date)}
