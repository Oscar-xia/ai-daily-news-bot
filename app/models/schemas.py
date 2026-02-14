"""
SQLAlchemy models and Pydantic schemas for AI Daily News Bot.
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, ConfigDict

from app.database import Base


# =============================================================================
# SQLAlchemy Models (Database Tables)
# =============================================================================

class Source(Base):
    """Information source configuration (RSS, Twitter, Search)."""
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON config
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    raw_items: Mapped[List["RawItem"]] = relationship("RawItem", back_populates="source")

    __table_args__ = (
        CheckConstraint("type IN ('rss', 'twitter', 'search')", name="check_source_type"),
    )


class RawItem(Base):
    """Raw collected information before processing."""
    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("sources.id"), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True, unique=True)
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="raw_items")
    processed_item: Mapped[Optional["ProcessedItem"]] = relationship("ProcessedItem", back_populates="raw_item", uselist=False)

    __table_args__ = (
        CheckConstraint("category IN ('ai', 'investment', 'web3', 'mixed')", name="check_category"),
        CheckConstraint("status IN ('pending', 'processed', 'discarded')", name="check_status"),
    )


class ProcessedItem(Base):
    """AI-processed information with summary, keywords, and score."""
    __tablename__ = "processed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_items.id"), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array
    score: Mapped[int] = mapped_column(Integer, default=0)
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    raw_item: Mapped["RawItem"] = relationship("RawItem", back_populates="processed_item")
    report_items: Mapped[List["ReportItem"]] = relationship("ReportItem", back_populates="processed_item")


class Report(Base):
    """Generated daily report."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Markdown content
    status: Mapped[str] = mapped_column(String(50), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    report_items: Mapped[List["ReportItem"]] = relationship("ReportItem", back_populates="report")

    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published')", name="check_report_status"),
    )


class ReportItem(Base):
    """Association between reports and processed items."""
    __tablename__ = "report_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), nullable=False)
    processed_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("processed_items.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    report: Mapped["Report"] = relationship("Report", back_populates="report_items")
    processed_item: Mapped["ProcessedItem"] = relationship("ProcessedItem", back_populates="report_items")


# =============================================================================
# Pydantic Schemas (API Request/Response)
# =============================================================================

class SourceBase(BaseModel):
    """Base schema for Source."""
    name: str
    type: str
    url: Optional[str] = None
    config: Optional[str] = None
    enabled: bool = True


class SourceCreate(SourceBase):
    """Schema for creating a Source."""
    pass


class SourceResponse(SourceBase):
    """Schema for Source response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_fetched_at: Optional[datetime] = None
    created_at: datetime


class RawItemBase(BaseModel):
    """Base schema for RawItem."""
    title: str
    content: Optional[str] = None
    url: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    category: Optional[str] = None


class RawItemCreate(RawItemBase):
    """Schema for creating a RawItem."""
    source_id: Optional[int] = None


class RawItemResponse(RawItemBase):
    """Schema for RawItem response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: Optional[int] = None
    status: str
    fetched_at: datetime
    created_at: datetime


class ProcessedItemBase(BaseModel):
    """Base schema for ProcessedItem."""
    summary: Optional[str] = None
    keywords: Optional[List[str]] = None
    score: int = 0
    is_duplicate: bool = False
    approved: bool = False


class ProcessedItemCreate(ProcessedItemBase):
    """Schema for creating a ProcessedItem."""
    raw_item_id: int


class ProcessedItemResponse(ProcessedItemBase):
    """Schema for ProcessedItem response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_item_id: int
    processed_at: datetime

    # Include related raw item info
    raw_item: Optional[RawItemResponse] = None


class ReportBase(BaseModel):
    """Base schema for Report."""
    report_date: date
    title: Optional[str] = None
    content: Optional[str] = None
    status: str = "draft"


class ReportCreate(ReportBase):
    """Schema for creating a Report."""
    pass


class ReportResponse(ReportBase):
    """Schema for Report response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    published_at: Optional[datetime] = None
    items: List[ProcessedItemResponse] = []


class ReportGenerateRequest(BaseModel):
    """Schema for report generation request."""
    date: Optional[date] = None
    min_score: int = 50
    categories: Optional[List[str]] = None


class CollectRequest(BaseModel):
    """Schema for manual collection request."""
    source_type: Optional[str] = None  # rss, twitter, search, all
    source_id: Optional[int] = None


class ProcessRequest(BaseModel):
    """Schema for manual processing request."""
    item_ids: Optional[List[int]] = None
    min_score_threshold: int = 0
