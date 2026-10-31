"""Application configuration.

All secrets and environment-driven values live here, on the backend.
The frontend never reads any of these values directly.
"""

from __future__ import annotations

from functools import lru_cache

from dotenv import find_dotenv, load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load `.env` from the current working directory upwards so the app works when
# started from `backend/` or from the repository root. Missing file is fine.
load_dotenv(find_dotenv(usecwd=True), override=False)


class Settings(BaseSettings):
    """Runtime settings, sourced from environment variables / `.env`."""

    model_config = SettingsConfigDict(extra="ignore", case_sensitive=False)

    app_name: str = "B2B Lead Engine"
    app_version: str = "0.1.0"
    backend_port: int = 8000
    frontend_origin: str = "http://127.0.0.1:5173"
    database_url: str = "sqlite:///./b2b_lead_engine.db"

    # Safety: the prototype is dry-run only. This must stay true.
    dry_run: bool = True

    # Discovery connectors
    tavily_api_key: str = ""
    exa_api_key: str = ""
    brave_api_key: str = ""
    remoteok_enabled: bool = True

    # Enrichment connectors
    gnews_api_key: str = ""
    open_corporates_api_key: str = ""
    sec_user_agent: str = "B2BLeadEngine/1.0"

    # AI provider (Groq)
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    groq_temperature: float = 0.1
    groq_max_tokens: int = 4096


@lru_cache
def get_settings() -> Settings:
    return Settings()