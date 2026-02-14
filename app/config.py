"""
Configuration management module.
Loads environment variables and provides configuration objects.
"""

from typing import List, Optional
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/news.db"

    # LLM Configuration
    llm_provider: str = "openai"
    openai_api_key: Optional[str] = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o"
    zhipu_api_key: Optional[str] = None
    zhipu_model: str = "glm-4"
    dashscope_api_key: Optional[str] = None
    qwen_model: str = "qwen-max"

    # Tavily API
    tavily_api_key: Optional[str] = None

    # RSSHub
    rsshub_base_url: str = "https://rsshub.app"

    # Apify
    apify_api_token: Optional[str] = None

    # Twitter
    twitter_users: str = ""

    # Scheduler
    scheduler_enabled: bool = True
    collect_interval_hours: int = 2
    report_generation_hour: int = 6

    # Logging
    log_level: str = "INFO"
    log_file: str = "logs/app.log"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def twitter_user_list(self) -> List[str]:
        """Parse Twitter usernames into a list."""
        if not self.twitter_users:
            return []
        return [u.strip() for u in self.twitter_users.split(",") if u.strip()]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Export settings instance
settings = get_settings()
