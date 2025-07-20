"""Typed, env‑driven configuration using **pydantic‑settings** (compatible with pydantic v2)."""
from pathlib import Path
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Flask ----------------------------------------------------------
    SECRET_KEY: SecretStr = "l2-secret-for-session"

    # Anki -----------------------------------------------------------
    ANKI_MODEL: str = "*L2: 2025 Revamp"
    ANKICONNECT_ENDPOINT: str = "http://localhost:8765"

    # Google CSE -----------------------------------------------------
    GOOGLE_CSE_KEY: SecretStr
    GOOGLE_CSE_CX: str

    # Forvo ----------------------------------------------------------
    FORVO_API_KEY: SecretStr

    # Executor -------------------------------------------------------
    MAX_WORKERS: int = 6

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()