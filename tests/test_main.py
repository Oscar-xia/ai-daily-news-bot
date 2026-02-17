"""
Basic tests for AI Daily News Bot.
"""

import pytest
from pathlib import Path


class TestBasic:
    """Basic sanity tests."""

    def test_project_structure(self):
        """Test that required directories exist."""
        project_root = Path(__file__).parent.parent

        assert (project_root / "app").is_dir()
        assert (project_root / "scripts").is_dir()
        assert (project_root / "frontend").is_dir()
        assert (project_root / "requirements.txt").is_file()

    def test_app_modules_exist(self):
        """Test that core app modules exist."""
        project_root = Path(__file__).parent.parent

        assert (project_root / "app" / "main.py").is_file()
        assert (project_root / "app" / "config.py").is_file()
        assert (project_root / "app" / "database.py").is_file()
        assert (project_root / "app" / "scheduler.py").is_file()


class TestConfig:
    """Tests for configuration module."""

    def test_config_import(self):
        """Test that config can be imported."""
        from app.config import settings

        assert settings is not None

    def test_config_defaults(self):
        """Test that config has expected defaults."""
        from app.config import settings

        assert hasattr(settings, 'scheduler_enabled')
        assert hasattr(settings, 'collect_interval_hours')
        assert hasattr(settings, 'report_generation_hour')


class TestDatabase:
    """Tests for database module."""

    def test_database_import(self):
        """Test that database module can be imported."""
        from app.database import async_session, get_session

        assert async_session is not None
        assert get_session is not None


class TestModels:
    """Tests for data models."""

    def test_models_import(self):
        """Test that models can be imported."""
        from app.models.schemas import Source, RawItem, ProcessedItem, Report

        assert Source is not None
        assert RawItem is not None
        assert ProcessedItem is not None
        assert Report is not None


class TestCollectors:
    """Tests for collector modules."""

    def test_base_collector_import(self):
        """Test that base collector can be imported."""
        from app.collectors.base import BaseCollector, CollectedItem

        assert BaseCollector is not None
        assert CollectedItem is not None


class TestLLM:
    """Tests for LLM module."""

    def test_llm_import(self):
        """Test that LLM module can be imported."""
        from app.llm.base import BaseLLM

        assert BaseLLM is not None

    def test_prompts_import(self):
        """Test that prompts module can be imported."""
        from app.llm.prompts import (
            get_scoring_prompt,
            get_summary_prompt,
            get_highlights_prompt,
        )

        assert get_scoring_prompt is not None
        assert get_summary_prompt is not None
        assert get_highlights_prompt is not None
