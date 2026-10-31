"""Groq API client with async support, retries, caching, and cost tracking."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional, Type, TypeVar

from groq import AsyncGroq
from groq.types.chat import ChatCompletion
from pydantic import BaseModel, ValidationError

from ..config import get_settings

T = TypeVar("T", bound="BaseModel")


@dataclass
class GroqUsage:
    """Token usage and cost information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    latency_ms: int = 0


@dataclass
class GroqResponse:
    """Structured response from Groq API."""
    content: str
    usage: GroqUsage
    model: str
    finish_reason: str


# Groq pricing (per 1M tokens) - update as needed
GROQ_PRICING = {
    "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},  # per 1M tokens
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "llama-3.3-70b-instruct": {"input": 0.59, "output": 0.79},
    "meta-llama/llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
    "mixtral-8x7b-32768": {"input": 0.27, "output": 0.27},
}


class GroqService:
    """Async Groq client with retries, caching, and cost tracking."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openai/gpt-oss-120b",
        temperature: float = 0.1,
        max_tokens: int = 4096,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        cache_ttl: int = 3600,  # 1 hour
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.cache_ttl = cache_ttl

        if not self.api_key:
            raise ValueError("GROQ_API_KEY not configured")

        self.client = AsyncGroq(api_key=self.api_key)
        self._cache: dict[str, tuple[Any, float]] = {}
        self._usage_log: list[dict] = []

    def _cache_key(self, messages: list[dict], **kwargs) -> str:
        """Generate cache key from messages and parameters."""
        key_data = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            **kwargs,
        }
        return hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached response if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return value
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        """Set cache entry with timestamp."""
        self._cache[key] = (value, time.time())

    def _calculate_cost(self, usage: GroqUsage) -> float:
        """Calculate estimated cost in USD."""
        pricing = GROQ_PRICING.get(self.model, {"input": 0.0, "output": 0.0})
        input_cost = (usage.prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (usage.completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def _log_usage(self, operation: str, usage: GroqUsage, latency_ms: int, success: bool, error: Optional[str] = None) -> None:
        """Log usage for monitoring."""
        self._usage_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "model": self.model,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "estimated_cost_usd": usage.estimated_cost_usd,
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        })

    async def _completion_with_retry(
        self,
        messages: list[dict],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> ChatCompletion:
        """Execute completion with exponential backoff retry."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature if temperature is not None else self.temperature,
                    max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
                    **kwargs
                )
                return response
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2 ** attempt), self.max_delay)
                    await asyncio.sleep(delay)
                else:
                    break

        raise last_exception

    async def complete(
        self,
        messages: list[dict],
        use_cache: bool = True,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> GroqResponse:
        """Execute chat completion with optional caching."""
        start_time = time.time()

        cache_key = self._cache_key(messages, **kwargs) if use_cache else None

        if use_cache and cache_key:
            cached = self._get_cached(cache_key)
            if cached:
                return cached

        try:
            response = await self._completion_with_retry(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs
            )
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            usage = GroqUsage(latency_ms=latency_ms)
            self._log_usage("completion", usage, latency_ms, False, str(e))
            raise

        latency_ms = int((time.time() - start_time) * 1000)

        # Extract usage
        usage_data = response.usage
        usage = GroqUsage(
            prompt_tokens=usage_data.prompt_tokens if usage_data else 0,
            completion_tokens=usage_data.completion_tokens if usage_data else 0,
            total_tokens=usage_data.total_tokens if usage_data else 0,
        )
        usage.estimated_cost_usd = self._calculate_cost(usage)
        usage.latency_ms = latency_ms

        content = response.choices[0].message.content or ""
        finish_reason = response.choices[0].finish_reason or "unknown"

        response_obj = GroqResponse(
            content=content,
            usage=usage,
            model=response.model,
            finish_reason=finish_reason,
        )

        if use_cache and cache_key:
            self._set_cache(cache_key, response_obj)

        self._log_usage("completion", usage, latency_ms, True)

        return response_obj

    async def structured_completion(
        self,
        messages: list[dict],
        response_model: Type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        use_cache: bool = True,
    ) -> T:
        """Execute completion with JSON schema validation."""
        schema = response_model.model_json_schema()
        
        messages_with_schema = messages + [{
            "role": "system",
            "content": f"Respond with valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"
        }]

        response = await self.complete(
            messages=messages_with_schema,
            temperature=temperature or self.temperature,
            max_tokens=max_tokens or self.max_tokens,
            use_cache=use_cache,
        )

        try:
            data = json.loads(response.content)
            return response_model.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as e:
            # Try one more time with explicit correction
            correction_prompt = f"Previous response was invalid JSON. Error: {e}. Please respond with valid JSON only."
            messages_with_correction = messages + [
                {"role": "assistant", "content": response.content},
                {"role": "user", "content": correction_prompt}
            ]
            response = await self.complete(
                messages=messages_with_correction,
                temperature=temperature or self.temperature,
                max_tokens=max_tokens or self.max_tokens,
                use_cache=False,
            )
            data = json.loads(response.content)
            return response_model.model_validate(data)

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        max_iterations: int = 5,
        tool_choice: str = "auto",
    ) -> dict:
        """Execute tool-calling loop with max iterations."""
        iteration = 0
        current_messages = messages.copy()

        while iteration < max_iterations:
            response = await self.complete(
                messages=current_messages,
                tools=tools,
                tool_choice=tool_choice,
                use_cache=False,
            )

            # Parse tool calls from response
            # This is simplified - actual implementation depends on Groq's tool calling format
            # For now, return the response for manual tool handling
            return {
                "content": response.content,
                "tool_calls": getattr(response, "tool_calls", None),
                "finish_reason": response.finish_reason,
            }

    def get_usage_stats(self) -> dict:
        """Get aggregated usage statistics."""
        total_tokens = sum(u["total_tokens"] for u in self._usage_log)
        total_cost = sum(u["estimated_cost_usd"] for u in self._usage_log)
        total_latency = sum(u["latency_ms"] for u in self._usage_log)
        successful = sum(1 for u in self._usage_log if u["success"])
        failed = len(self._usage_log) - successful

        return {
            "total_calls": len(self._usage_log),
            "successful_calls": successful,
            "failed_calls": failed,
            "total_tokens": total_tokens,
            "total_estimated_cost_usd": round(total_cost, 6),
            "average_latency_ms": total_latency / len(self._usage_log) if self._usage_log else 0,
        }

    def clear_cache(self) -> None:
        """Clear response cache."""
        self._cache.clear()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.close()


# Singleton instance
_groq_service: Optional[GroqService] = None


def get_groq_service(
    api_key: Optional[str] = None,
    model: str = "openai/gpt-oss-120b",
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> GroqService:
    """Get or create the Groq service singleton."""
    global _groq_service
    if _groq_service is None:
        _groq_service = GroqService(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    return _groq_service


def reset_groq_service() -> None:
    """Reset the singleton (useful for testing)."""
    global _groq_service
    _groq_service = None