"""
LLM base module for AI Daily News Bot.
Provides unified interface for multiple LLM providers.
"""

import httpx
import json
import asyncio
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Generator

from app.config import settings


class LLMError(Exception):
    """Custom exception for LLM errors."""
    pass


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send chat completion request."""
        pass

    async def chat_with_retry(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> str:
        """Send chat request with retry logic."""
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.chat(messages, temperature, max_tokens)
            except (httpx.HTTPError, LLMError) as e:
                last_error = e
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay * (attempt + 1))

        raise LLMError(f"Failed after {max_retries} retries: {last_error}")


class OpenAILLM(BaseLLM):
    """OpenAI-compatible LLM provider (supports OpenAI, 智谱, 通义)."""

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send chat completion request to OpenAI-compatible API."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise LLMError(f"API error: {response.status_code} - {response.text}")

            data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise LLMError(f"Invalid response format: {e}")


class ZhipuLLM(BaseLLM):
    """智谱 AI (GLM) provider."""

    def __init__(self, api_key: str, model: str = "glm-4"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://open.bigmodel.cn/api/paas/v4"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2000,
    ) -> str:
        """Send chat completion request to 智谱 API."""
        url = f"{self.base_url}/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=headers, json=payload)

            if response.status_code != 200:
                raise LLMError(f"API error: {response.status_code} - {response.text}")

            data = response.json()

            try:
                return data["choices"][0]["message"]["content"]
            except (KeyError, IndexError) as e:
                raise LLMError(f"Invalid response format: {e}")


def get_llm() -> BaseLLM:
    """Get LLM instance based on configuration."""
    provider = settings.llm_provider.lower()

    if provider == "openai":
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY not configured")

        return OpenAILLM(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )

    elif provider == "zhipu":
        if not settings.zhipu_api_key:
            raise LLMError("ZHIPU_API_KEY not configured")

        return ZhipuLLM(
            api_key=settings.zhipu_api_key,
            model=settings.zhipu_model,
        )

    elif provider == "qwen":
        if not settings.dashscope_api_key:
            raise LLMError("DASHSCOPE_API_KEY not configured")

        # 通义千问使用 OpenAI 兼容接口
        return OpenAILLM(
            api_key=settings.dashscope_api_key,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model=settings.qwen_model,
        )

    else:
        raise LLMError(f"Unknown LLM provider: {provider}")


# Convenience function for quick chat
async def chat(
    messages: List[Dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Send chat message using configured LLM provider."""
    llm = get_llm()
    return await llm.chat_with_retry(messages, temperature, max_tokens)


async def simple_chat(
    prompt: str,
    system_prompt: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    """Simple chat with a single prompt."""
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    return await chat(messages, temperature, max_tokens)
