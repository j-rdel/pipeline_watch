"""Runtime configuration loaded from environment (.env) via pydantic-settings.

Every setting has a safe default so the app boots with just `.env.example`
copied to `.env`. Secrets (GITHUB_TOKEN, DISCORD_WEBHOOK_URL) intentionally
default to empty and are only read by the modules that need them, so a bad
config surfaces at use-time with a clear error, not at import-time.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ollama_model: str = "qwen3:8b"
    ollama_host: str = "http://localhost:11434"
    ollama_temperature: float = 0.2

    pw_dry_run: bool = True
    pw_allowlist_paths: str = ".github/workflows/,requirements.txt,pyproject.toml,uv.lock"


settings = Settings()
