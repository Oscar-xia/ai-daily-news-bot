"""
SQLAlchemy models and Pydantic schemas for AI Daily News Bot.
Version 2.0 - 重构版
"""

from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Date, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pydantic import BaseModel, ConfigDict

from app.database import Base


# =============================================================================
# 分类常量
# =============================================================================

# 新的分类体系（来自 ai-daily-digest）
CATEGORY_AI_ML = "ai-ml"
CATEGORY_SECURITY = "security"
CATEGORY_ENGINEERING = "engineering"
CATEGORY_TOOLS = "tools"
CATEGORY_OPINION = "opinion"
CATEGORY_OTHER = "other"

VALID_CATEGORIES = [
    CATEGORY_AI_ML,
    CATEGORY_SECURITY,
    CATEGORY_ENGINEERING,
    CATEGORY_TOOLS,
    CATEGORY_OPINION,
    CATEGORY_OTHER,
]

CATEGORY_META = {
    CATEGORY_AI_ML: {"emoji": "🤖", "label": "AI / ML", "description": "AI、机器学习、LLM、深度学习"},
    CATEGORY_SECURITY: {"emoji": "🔒", "label": "安全", "description": "安全、隐私、漏洞、加密"},
    CATEGORY_ENGINEERING: {"emoji": "⚙️", "label": "工程", "description": "软件工程、架构、编程语言、系统设计"},
    CATEGORY_TOOLS: {"emoji": "🛠", "label": "工具 / 开源", "description": "开发工具、开源项目、新库/框架"},
    CATEGORY_OPINION: {"emoji": "💡", "label": "观点 / 杂谈", "description": "行业观点、个人思考、职业发展"},
    CATEGORY_OTHER: {"emoji": "📝", "label": "其他", "description": "不属于以上分类"},
}


# =============================================================================
# SQLAlchemy Models (Database Tables)
# =============================================================================

class Source(Base):
    """Information source configuration (RSS feeds)."""
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, default="rss")
    url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON config
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)  # 是否为默认源（90个精选源）
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationship
    raw_items: Mapped[List["RawItem"]] = relationship("RawItem", back_populates="source")

    __table_args__ = (
        CheckConstraint("type IN ('rss', 'custom')", name="check_source_type"),
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
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, scored, discarded
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    source: Mapped[Optional["Source"]] = relationship("Source", back_populates="raw_items")
    processed_item: Mapped[Optional["ProcessedItem"]] = relationship("ProcessedItem", back_populates="raw_item", uselist=False)

    __table_args__ = (
        CheckConstraint("status IN ('pending', 'scored', 'discarded')", name="check_status"),
    )


class ProcessedItem(Base):
    """AI-processed information with 3-dimension scoring, summary, and keywords."""
    __tablename__ = "processed_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_item_id: Mapped[int] = mapped_column(Integer, ForeignKey("raw_items.id"), nullable=False)

    # 三维评分（1-10 分，总分 3-30）
    relevance: Mapped[int] = mapped_column(Integer, default=5)      # 相关性
    quality: Mapped[int] = mapped_column(Integer, default=5)        # 质量
    timeliness: Mapped[int] = mapped_column(Integer, default=5)     # 时效性
    total_score: Mapped[int] = mapped_column(Integer, default=15)   # 总分 = 上述三项之和

    # 分类和关键词
    category: Mapped[str] = mapped_column(String(50), default=CATEGORY_OTHER)
    keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array

    # 内容处理
    title_zh: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 中文标题
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)   # 摘要
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)    # 推荐理由

    # 元数据
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    raw_item: Mapped["RawItem"] = relationship("RawItem", back_populates="processed_item")
    report_items: Mapped[List["ReportItem"]] = relationship("ReportItem", back_populates="processed_item")

    __table_args__ = (
        CheckConstraint(f"category IN ({', '.join(repr(c) for c in VALID_CATEGORIES)})", name="check_category"),
    )


class Report(Base):
    """Generated daily report."""
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Markdown content

    # 趋势总结
    highlights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # 今日看点

    status: Mapped[str] = mapped_column(String(50), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
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
    type: str = "rss"
    url: Optional[str] = None
    config: Optional[str] = None
    is_default: bool = False
    enabled: bool = True


class SourceCreate(SourceBase):
    """Schema for creating a Source."""
    pass


class SourceUpdate(BaseModel):
    """Schema for updating a Source."""
    name: Optional[str] = None
    type: Optional[str] = None
    url: Optional[str] = None
    config: Optional[str] = None
    enabled: Optional[bool] = None


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


class RawItemCreate(RawItemBase):
    """Schema for creating a RawItem."""
    source_id: Optional[int] = None


class RawItemResponse(RawItemBase):
    """Schema for RawItem response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: Optional[int] = None
    source_name: Optional[str] = None
    status: str
    fetched_at: datetime
    created_at: datetime


class ProcessedItemBase(BaseModel):
    """Base schema for ProcessedItem."""
    relevance: int = 5
    quality: int = 5
    timeliness: int = 5
    total_score: int = 15
    category: str = CATEGORY_OTHER
    keywords: Optional[List[str]] = None
    title_zh: Optional[str] = None
    summary: Optional[str] = None
    reason: Optional[str] = None
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
    raw_item: Optional[RawItemResponse] = None


class ReportBase(BaseModel):
    """Base schema for Report."""
    report_date: date
    title: Optional[str] = None
    content: Optional[str] = None
    highlights: Optional[str] = None
    status: str = "draft"


class ReportCreate(ReportBase):
    """Schema for creating a Report."""
    pass


class ReportResponse(ReportBase):
    """Schema for Report response."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    version: int
    created_at: datetime
    published_at: Optional[datetime] = None
    items: List[ProcessedItemResponse] = []


class ReportGenerateRequest(BaseModel):
    """Schema for report generation request."""
    report_date: Optional[date] = None
    min_score: int = 20  # 最低总分（3-30分制）
    top_n: int = 15  # 精选文章数
    hours: int = 48  # 时间范围（小时）


class CollectRequest(BaseModel):
    """Schema for manual collection request."""
    source_id: Optional[int] = None
    hours: int = 48  # 时间范围（小时）


class ProcessRequest(BaseModel):
    """Schema for manual processing request."""
    item_ids: Optional[List[int]] = None
    min_score_threshold: int = 15  # 最低总分
    top_n: int = 15  # 精选文章数
