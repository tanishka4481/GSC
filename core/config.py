"""
PROVCHAIN — Configuration Management
=====================================
Single source of truth for all environment variables, API keys, and thresholds.
Uses pydantic-settings to load from .env file with type validation.

Rule: NEVER hardcode API keys anywhere else — always import from here.
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # App
    # -------------------------------------------------------------------------
    APP_NAME: str = "PROVCHAIN"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # -------------------------------------------------------------------------
    # Google Cloud Platform
    # -------------------------------------------------------------------------
    GOOGLE_CLOUD_PROJECT: str = ""
    GCP_REGION: str = "asia-south1"

    # -------------------------------------------------------------------------
    # Gemini API
    # -------------------------------------------------------------------------
    GEMINI_API_KEY: str = ""

    # -------------------------------------------------------------------------
    # Vertex AI Matching Engine
    # -------------------------------------------------------------------------
    VERTEX_INDEX_ID: str = ""
    VERTEX_ENDPOINT_ID: str = ""

    # -------------------------------------------------------------------------
    # Firebase
    # -------------------------------------------------------------------------
    FIREBASE_CREDENTIALS_PATH: str = ""

    # -------------------------------------------------------------------------
    # IPFS (Pinata)
    # -------------------------------------------------------------------------
    PINATA_JWT: str = ""
    PINATA_API_URL: str = "https://api.pinata.cloud"

    # -------------------------------------------------------------------------
    # Google Custom Search
    # -------------------------------------------------------------------------
    CUSTOM_SEARCH_API_KEY: str = ""
    CUSTOM_SEARCH_CX: str = ""

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173"]
    )

    # -------------------------------------------------------------------------
    # Rate Limiting
    # -------------------------------------------------------------------------
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_WINDOW_SECONDS: int = 60

    # -------------------------------------------------------------------------
    # Match Decision Thresholds
    # -------------------------------------------------------------------------
    # These control match_decision() — the ONLY function that flags content.
    PHASH_HIGH_CONFIDENCE: float = 0.92
    EMBEDDING_PROBABLE_MATCH: float = 0.88
    PHASH_POSSIBLE_MATCH: float = 0.75
    EMBEDDING_POSSIBLE_MATCH: float = 0.75
    DMCA_MIN_URLS: int = 2


@lru_cache()
def get_settings() -> Settings:
    """
    Cached singleton accessor for application settings.

    Usage:
        from core.config import get_settings
        settings = get_settings()
        print(settings.GEMINI_API_KEY)
    """
    return Settings()
