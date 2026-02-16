"""
Configuration management module.
Loads environment variables and provides configuration objects.
"""

from typing import Optional, List
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/news.db"

    # LLM Configuration - 硅基流动 (SiliconFlow)
    llm_provider: str = "siliconflow"
    siliconflow_api_key: Optional[str] = None
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model: str = "Qwen/Qwen3-30B-A3B-Instruct-2507"

    # RSSHub (for RSS feeds)
    rsshub_base_url: str = "https://rsshub.app"

    # Scheduler
    scheduler_enabled: bool = True
    collect_interval_hours: int = 2
    report_generation_hour: int = 6

    # Processing parameters
    collect_limit: int = 50
    report_min_score: int = 15  # 参考分数线（3-30分制）
    report_top_n: int = 15  # 目标精选数
    process_hours: int = 24  # 采集时间范围（小时）
    process_batch_size: int = 20
    dedup_days: int = 7

    # Collection limits per source
    collect_limit_per_source: int = 15  # 每个源最多采集条数

    # Rule-based filter (初筛)
    filter_max_age_hours: int = 48  # 只保留多少小时内的新闻
    filter_title_min_length: int = 10  # 标题最少字数
    filter_content_min_length: int = 50  # 内容最少字数

    # AI filter (次筛)
    ai_min_score: int = 60  # AI 评分最低阈值

    # Report limits (精选)
    report_max_total: int = 25  # 日报最多总条数
    report_max_ai: int = 12  # AI 分类最多条数
    report_max_investment: int = 8  # 投资分类最多条数
    report_max_web3: int = 5  # Web3 分类最多条数

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    # Email notification (SMTP)
    email_enabled: bool = False  # 是否启用邮件推送
    email_sender: Optional[str] = None  # 发件人邮箱
    email_sender_name: str = "AI技术日报"  # 发件人显示名称
    email_password: Optional[str] = None  # 邮箱授权码/密码
    email_receivers: str = ""  # 收件人列表（逗号分隔）
    email_smtp_server: Optional[str] = None  # SMTP 服务器（留空自动识别）
    email_smtp_port: int = 465  # SMTP 端口

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def email_receiver_list(self) -> List[str]:
        """Parse email receivers into a list."""
        if not self.email_receivers:
            return [self.email_sender] if self.email_sender else []
        return [r.strip() for r in self.email_receivers.split(",") if r.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance
settings = get_settings()
