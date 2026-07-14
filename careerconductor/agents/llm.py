"""Shared Anthropic call helper: one retry policy for every agent node.

Retries only transient failures (connection drops, rate limits, 5xx). Permanent
errors (bad request, auth) surface immediately so the per-job try/except in each
node can log them without burning retry time.
"""
from __future__ import annotations

import anthropic
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from careerconductor.config.settings import settings

_TRANSIENT_ERRORS = (
    anthropic.APIConnectionError,
    anthropic.RateLimitError,
    anthropic.InternalServerError,
)


@retry(
    retry=retry_if_exception_type(_TRANSIENT_ERRORS),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def claude_call(
    client: anthropic.Anthropic,
    *,
    system: list | None = None,
    user_content: str,
    max_tokens: int,
) -> str:
    kwargs = {
        "model": settings.anthropic_model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": user_content}],
    }
    if system is not None:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text


def cached_system_block(text: str) -> list:
    """System block marked for Anthropic prompt caching (reused across calls in a run)."""
    return [{"type": "text", "text": text, "cache_control": {"type": "ephemeral"}}]
