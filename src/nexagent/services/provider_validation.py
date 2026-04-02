"""Lightweight provider/model validation for sub-agents."""

from __future__ import annotations

import asyncio
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from nexagent.services.crypto import decrypt_api_key
from nexagent.services.sub_agent_service import get_sub_agent

VALIDATION_TIMEOUT = 10  # seconds


class ProviderValidationError(Exception):
    pass


async def validate_provider(
    db: AsyncSession,
    agent_id: uuid.UUID,
) -> dict:
    """Validate that a sub-agent's LLM config is reachable.

    Sends a minimal prompt to the configured provider/model to verify
    connectivity and authentication. Returns a result dict.
    """
    agent = await get_sub_agent(db, agent_id)

    api_key: str | None = None
    if agent.api_key_encrypted:
        api_key = decrypt_api_key(agent.api_key_encrypted)

    try:
        result = await asyncio.wait_for(
            _test_provider(agent.provider, agent.model_name, api_key),
            timeout=VALIDATION_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        return {"valid": False, "error": f"Provider '{agent.provider}' did not respond within {VALIDATION_TIMEOUT}s"}
    except Exception as e:
        return {"valid": False, "error": str(e)}


async def _test_provider(provider: str, model_name: str, api_key: str | None) -> dict:
    """Send a minimal test request to the provider."""
    if provider == "openai":
        return await _test_openai(model_name, api_key)
    elif provider == "anthropic":
        return await _test_anthropic(model_name, api_key)
    elif provider == "litellm":
        return await _test_litellm(model_name, api_key)
    else:
        return {"valid": True, "message": f"Provider '{provider}' accepted (no automated check available)"}


async def _test_openai(model_name: str, api_key: str | None) -> dict:
    """Test OpenAI connectivity."""
    import httpx

    if not api_key:
        return {"valid": False, "error": "No API key configured for OpenAI"}

    async with httpx.AsyncClient(timeout=VALIDATION_TIMEOUT) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        )
    if resp.status_code == 200:
        return {"valid": True, "message": f"OpenAI model '{model_name}' is reachable"}
    elif resp.status_code == 401:
        return {"valid": False, "error": "Authentication failed — invalid API key"}
    elif resp.status_code == 404:
        return {"valid": False, "error": f"Model '{model_name}' not found"}
    else:
        return {"valid": False, "error": f"OpenAI returned status {resp.status_code}: {resp.text[:200]}"}


async def _test_anthropic(model_name: str, api_key: str | None) -> dict:
    """Test Anthropic connectivity."""
    import httpx

    if not api_key:
        return {"valid": False, "error": "No API key configured for Anthropic"}

    async with httpx.AsyncClient(timeout=VALIDATION_TIMEOUT) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        )
    if resp.status_code == 200:
        return {"valid": True, "message": f"Anthropic model '{model_name}' is reachable"}
    elif resp.status_code == 401:
        return {"valid": False, "error": "Authentication failed — invalid API key"}
    elif resp.status_code == 404:
        return {"valid": False, "error": f"Model '{model_name}' not found"}
    else:
        return {"valid": False, "error": f"Anthropic returned status {resp.status_code}: {resp.text[:200]}"}


async def _test_litellm(model_name: str, api_key: str | None) -> dict:
    """Test LiteLLM proxy connectivity."""
    import httpx

    from nexagent.config import settings

    base_url = settings.litellm_base_url
    if not base_url:
        return {"valid": False, "error": "LITELLM_BASE_URL not configured"}

    key = api_key or settings.litellm_api_key
    headers = {}
    if key:
        headers["Authorization"] = f"Bearer {key}"

    async with httpx.AsyncClient(timeout=VALIDATION_TIMEOUT) as client:
        resp = await client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json={"model": model_name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1},
        )
    if resp.status_code == 200:
        return {"valid": True, "message": f"LiteLLM model '{model_name}' is reachable"}
    else:
        return {"valid": False, "error": f"LiteLLM returned status {resp.status_code}: {resp.text[:200]}"}
