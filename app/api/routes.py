"""
API routes for AI Daily News Bot.
Version 2.0
"""

import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models.schemas import (
    Source, RawItem, ProcessedItem, Report,
    SourceCreate, SourceResponse, SourceUpdate,
    RawItemCreate, RawItemResponse,
    ProcessedItemResponse,
    ReportCreate, ReportResponse, ReportGenerateRequest,
    CATEGORY_META, VALID_CATEGORIES,
)
from app.config import settings


router = APIRouter()

# Path to .env file
ENV_FILE = Path(__file__).parent.parent.parent / ".env"


# =============================================================================
# Config API
# =============================================================================

class ConfigResponse(BaseModel):
    """Response model for config."""
    siliconflow_api_key: Optional[str] = None
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"
    scheduler_enabled: bool = True
    collect_interval_hours: int = 2
    report_generation_hour: int = 6
    report_min_score: int = 20  # 新的评分制 (3-30)
    report_top_n: int = 15
    process_hours: int = 48
    # Email config
    email_enabled: bool = False
    email_sender: Optional[str] = None
    email_sender_name: str = "AI技术日报"
    email_receivers: str = ""
    email_smtp_server: Optional[str] = None
    email_smtp_port: int = 465


class ConfigUpdate(BaseModel):
    """Update model for config."""
    siliconflow_api_key: Optional[str] = None
    siliconflow_base_url: Optional[str] = None
    siliconflow_model: Optional[str] = None
    scheduler_enabled: Optional[bool] = None
    collect_interval_hours: Optional[int] = None
    report_generation_hour: Optional[int] = None
    report_min_score: Optional[int] = None
    report_top_n: Optional[int] = None
    process_hours: Optional[int] = None
    # Email config
    email_enabled: Optional[bool] = None
    email_sender: Optional[str] = None
    email_sender_name: Optional[str] = None
    email_password: Optional[str] = None
    email_receivers: Optional[str] = None
    email_smtp_server: Optional[str] = None
    email_smtp_port: Optional[int] = None
    # Custom save path config
    custom_save_enabled: Optional[bool] = None
    custom_save_path: Optional[str] = None


def mask_api_key(key: str) -> str:
    """Mask API key for display."""
    if not key or len(key) < 8:
        return ""
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


@router.get("/config")
async def get_config():
    """Get current configuration (with masked API keys)."""
    return {
        "siliconflow_api_key": mask_api_key(settings.siliconflow_api_key or ""),
        "siliconflow_base_url": settings.siliconflow_base_url,
        "siliconflow_model": settings.siliconflow_model,
        "scheduler_enabled": settings.scheduler_enabled,
        "collect_interval_hours": settings.collect_interval_hours,
        "report_generation_hour": getattr(settings, 'report_generation_hour', 6),
        "report_min_score": getattr(settings, 'report_min_score', 20),
        "report_top_n": getattr(settings, 'report_top_n', 15),
        "process_hours": getattr(settings, 'process_hours', 48),
        # Email config
        "email_enabled": settings.email_enabled,
        "email_sender": settings.email_sender,
        "email_sender_name": settings.email_sender_name,
        "email_receivers": settings.email_receivers,
        "email_smtp_server": settings.email_smtp_server,
        "email_smtp_port": settings.email_smtp_port,
        "email_configured": bool(settings.email_sender and settings.email_password),
        # Custom save path config
        "custom_save_enabled": settings.custom_save_enabled,
        "custom_save_path": settings.custom_save_path,
    }


@router.put("/config")
async def update_config(config: ConfigUpdate):
    """Update configuration in .env file and reload settings."""
    updates = config.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    # Read current .env
    env_lines = []
    if ENV_FILE.exists():
        with open(ENV_FILE, "r") as f:
            env_lines = f.readlines()

    # Update or add each key
    updated_keys = set()
    for i, line in enumerate(env_lines):
        if "=" in line and not line.strip().startswith("#"):
            key = line.split("=")[0].strip()
            if key.upper() in [k.upper() for k in updates.keys()]:
                # Find the matching update key
                for update_key, value in updates.items():
                    if update_key.upper() == key.upper():
                        # Convert boolean to string for .env
                        if isinstance(value, bool):
                            str_value = "true" if value else "false"
                        else:
                            str_value = str(value) if value is not None else ""
                        env_lines[i] = f"{update_key.upper()}={str_value}\n"
                        updated_keys.add(update_key)
                        break

    # Add new keys
    for key, value in updates.items():
        if key not in updated_keys:
            if isinstance(value, bool):
                str_value = "true" if value else "false"
            else:
                str_value = str(value) if value is not None else ""
            env_lines.append(f"{key.upper()}={str_value}\n")

    # Write back to .env
    with open(ENV_FILE, "w") as f:
        f.writelines(env_lines)

    # Update settings object in memory
    from app.config import get_settings
    global settings
    # Clear the LRU cache and get fresh settings
    get_settings.cache_clear()
    settings = get_settings()

    return {"message": "Configuration updated", "updated": list(updates.keys())}


# =============================================================================
# Stats API
# =============================================================================

@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    """Get database statistics."""
    from datetime import datetime, timedelta

    # Count sources
    sources_result = await session.execute(select(func.count(Source.id)))
    sources = sources_result.scalar() or 0

    # Count raw items within 24h (recent articles)
    cutoff = datetime.utcnow() - timedelta(hours=24)
    recent_result = await session.execute(
        select(func.count(RawItem.id)).where(RawItem.published_at >= cutoff)
    )
    recent_24h = recent_result.scalar() or 0

    # Count all raw items (for cleanup stats)
    raw_result = await session.execute(select(func.count(RawItem.id)))
    raw_items = raw_result.scalar() or 0

    # Count pending items
    pending_result = await session.execute(
        select(func.count(RawItem.id)).where(RawItem.status == "pending")
    )
    pending = pending_result.scalar() or 0

    # Count approved (selected) items
    approved_result = await session.execute(
        select(func.count(ProcessedItem.id)).where(ProcessedItem.approved == True)
    )
    approved = approved_result.scalar() or 0

    # Count rejected items
    rejected_result = await session.execute(
        select(func.count(ProcessedItem.id)).where(ProcessedItem.approved == False)
    )
    rejected = rejected_result.scalar() or 0

    # Count reports
    reports_result = await session.execute(select(func.count(Report.id)))
    reports = reports_result.scalar() or 0

    return {
        "sources": sources,
        "recent_24h": recent_24h,  # 最近 24h 新文
        "approved": approved,       # 已精选
        "rejected": rejected,       # 未入选
        "raw_items": raw_items,     # 总数（用于清理）
        "pending": pending,
        "reports": reports,
    }


# =============================================================================
# Sources API
# =============================================================================

@router.get("/sources")
async def get_sources(
    enabled_only: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Get all sources."""
    query = select(Source).order_by(Source.id)

    if enabled_only:
        query = query.where(Source.enabled == True)

    result = await session.execute(query)
    sources = result.scalars().all()

    return [{
        "id": s.id,
        "name": s.name,
        "type": s.type,
        "url": s.url,
        "is_default": s.is_default,
        "enabled": s.enabled,
        "last_fetched_at": s.last_fetched_at.isoformat() if s.last_fetched_at else None,
    } for s in sources]


@router.post("/sources")
async def create_source(
    source: SourceCreate,
    session: AsyncSession = Depends(get_session)
):
    """Create a new source."""
    new_source = Source(
        name=source.name,
        type=source.type,
        url=source.url,
        config=source.config,
        is_default=False,  # User-created sources are not default
        enabled=source.enabled,
    )
    session.add(new_source)
    await session.commit()
    await session.refresh(new_source)

    return {"message": "Source created", "id": new_source.id}


@router.put("/sources/{source_id}")
async def update_source(
    source_id: int,
    source_update: SourceUpdate,
    session: AsyncSession = Depends(get_session)
):
    """Update a source."""
    result = await session.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalars().first()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    updates = source_update.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(source, key, value)

    await session.commit()
    return {"message": "Source updated"}


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a source."""
    result = await session.execute(
        select(Source).where(Source.id == source_id)
    )
    source = result.scalars().first()

    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if source.is_default:
        raise HTTPException(status_code=400, detail="Cannot delete default source")

    await session.delete(source)
    await session.commit()
    return {"message": "Source deleted"}


# =============================================================================
# Items API
# =============================================================================

@router.get("/items")
async def get_items(
    status: str = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_session)
):
    """Get raw items."""
    query = select(RawItem).order_by(RawItem.fetched_at.desc())

    if status:
        query = query.where(RawItem.status == status)

    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()

    return [{
        "id": item.id,
        "title": item.title,
        "url": item.url,
        "author": item.author,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "status": item.status,
        "fetched_at": item.fetched_at.isoformat() if item.fetched_at else None,
        "source_name": item.source.name if item.source else None,
    } for item in items]


@router.get("/items/{item_id}")
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

    return {
        "id": item.id,
        "title": item.title,
        "content": item.content,
        "url": item.url,
        "author": item.author,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "status": item.status,
        "fetched_at": item.fetched_at.isoformat() if item.fetched_at else None,
        "source_name": item.source.name if item.source else None,
    }


# =============================================================================
# Processed Items API
# =============================================================================

@router.get("/processed")
async def get_processed_items(
    min_score: int = 20,
    category: str = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session)
):
    """Get processed items."""
    query = select(ProcessedItem).where(ProcessedItem.total_score >= min_score)

    if category and category in VALID_CATEGORIES:
        query = query.where(ProcessedItem.category == category)

    query = query.order_by(ProcessedItem.total_score.desc()).limit(limit)

    result = await session.execute(query)
    items = result.scalars().all()

    # Load raw items
    response = []
    for item in items:
        raw_result = await session.execute(
            select(RawItem).where(RawItem.id == item.raw_item_id)
        )
        raw = raw_result.scalars().first()

        response.append({
            "id": item.id,
            "title_zh": item.title_zh,
            "title": raw.title if raw else None,
            "summary": item.summary,
            "reason": item.reason,
            "relevance": item.relevance,
            "quality": item.quality,
            "timeliness": item.timeliness,
            "total_score": item.total_score,
            "category": item.category,
            "category_label": CATEGORY_META.get(item.category, {}).get('label', item.category),
            "keywords": json.loads(item.keywords) if item.keywords else [],
            "url": raw.url if raw else None,
            "source_name": raw.source.name if raw and raw.source else None,
        })

    return response


# =============================================================================
# Reports API
# =============================================================================

@router.get("/reports")
async def get_reports(
    limit: int = 20,
    session: AsyncSession = Depends(get_session)
):
    """Get all reports (multiple versions per day supported)."""
    query = select(Report).order_by(
        Report.report_date.desc(),
        Report.version.desc()
    ).limit(limit)

    result = await session.execute(query)
    reports = result.scalars().all()

    # Group by date
    grouped = {}
    for report in reports:
        date_str = str(report.report_date)
        if date_str not in grouped:
            grouped[date_str] = {
                "date": date_str,
                "versions": []
            }
        grouped[date_str]["versions"].append({
            "id": report.id,
            "version": report.version,
            "title": report.title,
            "status": report.status,
            "highlights": report.highlights[:100] + "..." if report.highlights and len(report.highlights) > 100 else report.highlights,
            "created_at": report.created_at.isoformat() if report.created_at else None,
        })

    return list(grouped.values())


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific report by ID."""
    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": report.id,
        "report_date": str(report.report_date),
        "title": report.title,
        "content": report.content,
        "highlights": report.highlights,
        "status": report.status,
        "version": report.version,
        "created_at": report.created_at.isoformat() if report.created_at else None,
    }


@router.post("/reports/generate")
async def generate_report(
    request: ReportGenerateRequest = None,
    session: AsyncSession = Depends(get_session)
):
    """Generate a new report (creates a new version)."""
    from scripts.run_generator import run_generator

    report_date = request.report_date if request else None
    min_score = request.min_score if request else 20
    top_n = request.top_n if request else 15

    await run_generator(
        report_date=report_date,
        min_score=min_score,
        top_n=top_n,
    )

    return {"message": "Report generated", "date": str(report_date or date.today())}


@router.put("/reports/{report_id}/publish")
async def publish_report(
    report_id: int,
    send_email: bool = False,
    session: AsyncSession = Depends(get_session)
):
    """Publish a specific report and optionally send via email."""
    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    report.status = "published"
    await session.commit()

    response = {"message": "Report published", "id": report_id, "email_sent": False}

    # Send email if requested
    if send_email:
        from app.notification.email_sender import send_report, is_email_configured

        if is_email_configured():
            email_success = send_report(report.content, str(report.report_date))
            response["email_sent"] = email_success
            response["email_message"] = "Email sent successfully" if email_success else "Failed to send email"
        else:
            response["email_message"] = "Email not configured"

    return response


@router.delete("/reports/{report_id}")
async def delete_report(
    report_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Delete a specific report version."""
    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    await session.delete(report)
    await session.commit()

    return {"message": "Report deleted", "id": report_id}


# =============================================================================
# Actions API
# =============================================================================

@router.post("/collect")
async def run_collect():
    """Run RSS collection."""
    from scripts.run_collector import run_collectors

    count = await run_collectors()
    return {"message": "Collection completed", "count": count}


@router.post("/process")
async def run_process():
    """Run AI processing."""
    from scripts.run_processor import run_processor

    count = await run_processor()
    return {"message": "Processing completed", "count": count}


# =============================================================================
# Categories API
# =============================================================================

@router.get("/categories")
async def get_categories():
    """Get all available categories."""
    return [{"id": k, **v} for k, v in CATEGORY_META.items()]


# =============================================================================
# Cleanup API
# =============================================================================

class CleanupRequest(BaseModel):
    """Request model for cleanup action."""
    action: str
    days: int = 7


@router.get("/cleanup/stats")
async def get_cleanup_stats(session: AsyncSession = Depends(get_session)):
    """Get cleanup statistics."""
    from datetime import datetime, timedelta

    # Count by status
    pending_result = await session.execute(
        select(func.count(RawItem.id)).where(RawItem.status == "pending")
    )
    pending = pending_result.scalar() or 0

    discarded_result = await session.execute(
        select(func.count(RawItem.id)).where(RawItem.status == "discarded")
    )
    discarded = discarded_result.scalar() or 0

    scored_result = await session.execute(
        select(func.count(RawItem.id)).where(RawItem.status == "scored")
    )
    scored = scored_result.scalar() or 0

    # Total raw items
    total_result = await session.execute(select(func.count(RawItem.id)))
    total_raw = total_result.scalar() or 0

    # Items older than 7 days
    cutoff = datetime.utcnow() - timedelta(days=7)
    old_result = await session.execute(
        select(func.count(RawItem.id)).where(RawItem.fetched_at < cutoff)
    )
    old_items = old_result.scalar() or 0

    return {
        "pending": pending,
        "discarded": discarded,
        "processed": scored,
        "total_raw": total_raw,
        "old_items_7d": old_items,
    }


@router.post("/cleanup")
async def run_cleanup(
    request: CleanupRequest,
    session: AsyncSession = Depends(get_session)
):
    """Run cleanup action."""
    from datetime import datetime, timedelta

    action = request.action
    days = request.days
    deleted_count = 0
    cutoff = datetime.utcnow() - timedelta(days=days)

    if action == "pending":
        # Delete pending items
        result = await session.execute(
            delete(RawItem).where(RawItem.status == "pending")
        )
        deleted_count = result.rowcount

    elif action == "discarded":
        # Delete discarded items
        result = await session.execute(
            delete(RawItem).where(RawItem.status == "discarded")
        )
        deleted_count = result.rowcount

    elif action == "old_raw":
        # Delete items older than N days
        result = await session.execute(
            delete(RawItem).where(RawItem.fetched_at < cutoff)
        )
        deleted_count = result.rowcount

    elif action == "all_raw":
        # Delete all raw items (and cascade to processed items)
        await session.execute(delete(ProcessedItem))
        result = await session.execute(delete(RawItem))
        deleted_count = result.rowcount

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    await session.commit()

    return {"success": True, "deleted_count": deleted_count, "action": action}


# =============================================================================
# Email API
# =============================================================================

@router.post("/email/test")
async def test_email():
    """Send a test email."""
    import traceback

    try:
        from app.notification.email_sender import send_email, is_email_configured

        if not is_email_configured():
            raise HTTPException(
                status_code=400,
                detail="Email not configured. Please set EMAIL_ENABLED, EMAIL_SENDER, and EMAIL_PASSWORD."
            )

        content = f"""# 测试邮件

这是一封来自 **AI技术日报** 的测试邮件。

如果你收到这封邮件，说明邮件配置成功！

---
*发送时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        success = send_email(content, "AI技术日报 - 测试邮件")

        if success:
            return {"success": True, "message": "Test email sent successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to send test email - check server logs")

    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Email test error: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@router.post("/email/send-report/{report_id}")
async def send_report_email(
    report_id: int,
    session: AsyncSession = Depends(get_session)
):
    """Send a specific report via email."""
    from app.notification.email_sender import send_report, is_email_configured
    from pathlib import Path

    if not is_email_configured():
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Please set EMAIL_ENABLED, EMAIL_SENDER, and EMAIL_PASSWORD."
        )

    result = await session.execute(
        select(Report).where(Report.id == report_id)
    )
    report = result.scalars().first()

    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    success = send_report(report.content, str(report.report_date))

    # Also save to custom path if enabled
    custom_save_result = None
    if settings.custom_save_enabled and settings.custom_save_path:
        try:
            custom_path = Path(settings.custom_save_path)
            custom_path.mkdir(parents=True, exist_ok=True)
            custom_file = custom_path / f"AI技术日报-{report.report_date}.md"
            with open(custom_file, "w", encoding="utf-8") as f:
                f.write(report.content)
            custom_save_result = str(custom_file)
        except Exception as e:
            custom_save_result = f"error: {str(e)}"

    if success:
        message = f"Report sent to {settings.email_receiver_list}"
        if custom_save_result and not custom_save_result.startswith("error"):
            message += f", saved to {custom_save_result}"
        return {"success": True, "message": message, "custom_save_path": custom_save_result}
    else:
        raise HTTPException(status_code=500, detail="Failed to send report via email")
