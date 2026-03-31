"""Configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings read from env / .env file."""

    # LLM provider settings
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # LiteLLM proxy (optional — use to unify access to multiple models)
    litellm_base_url: str = ""
    litellm_api_key: str = ""

    # Default model to use (OpenAI-compatible model string)
    default_model: str = "gpt-4o"

    # LangSmith observability (optional)
    langchain_api_key: str = ""
    langchain_project: str = "nexagent"
    langchain_tracing_v2: str = "false"

    # Server
    host: str = "0.0.0.0"
    port: int = 8123

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
