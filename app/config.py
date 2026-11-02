"""Configuration module for Satyahd.

Loads environment variables from .env and exposes strongly typed settings.
Hard Rule 4: Secrets only in .env. Never print or log keys.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

# Base directory of the repository
BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env if present
load_dotenv(BASE_DIR / ".env")


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def _get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Meta Model API (Per Model API Docs: MODEL_API_KEY and https://api.meta.ai/v1)
    MODEL_API_KEY: str = os.getenv("MODEL_API_KEY") or os.getenv("META_API_KEY", "")
    META_API_KEY: str = os.getenv("MODEL_API_KEY") or os.getenv("META_API_KEY", "")  # alias for backwards compatibility
    META_API_BASE: str = os.getenv("META_API_BASE", "https://api.meta.ai/v1")

    # Standard Model IDs (Avoid -contributor IDs to preserve data privacy)
    MODEL_NAME: str = os.getenv("MODEL_NAME", "muse-spark-1.3")
    WONDER_MODEL: str = os.getenv("WONDER_MODEL", "muse-wonder-1.0")
    IMAGE_MODEL: str = os.getenv("IMAGE_MODEL", "muse-image-1.0")
    SAM_MODEL: str = os.getenv("SAM_MODEL", "sam-3.1")

    # Agent B Open-Weights (e.g. muse-glimmer-30b or partner credit endpoint)
    AGENT_B_BASE: str = os.getenv("AGENT_B_BASE", "")
    AGENT_B_KEY: str = os.getenv("AGENT_B_KEY", "")
    AGENT_B_MODEL: str = os.getenv("AGENT_B_MODEL", "muse-glimmer-30b")

    # Pre-filter
    PREFILTER_BASE: str = os.getenv("PREFILTER_BASE", "")
    PREFILTER_KEY: str = os.getenv("PREFILTER_KEY", "")
    PREFILTER_MODEL: str = os.getenv("PREFILTER_MODEL", "")

    # Audit & Security
    SIGNING_KEY_PATH: str = os.getenv("SIGNING_KEY_PATH", "ed25519_key.pem")
    ANCHOR_DIR: str = os.getenv("ANCHOR_DIR", "anchors")

    # Runtime & Mock
    DEMO_TODAY: str = os.getenv("DEMO_TODAY", "2026-11-01")
    ALLOW_MOCK: bool = _get_bool("ALLOW_MOCK", True)
    MODEL_TIMEOUT_SECONDS: int = _get_int("MODEL_TIMEOUT_SECONDS", 30)

    # Cost Tracking Constants (Per 1M tokens)
    COST_PER_M_INPUT_TOKENS: float = 0.15
    COST_PER_M_OUTPUT_TOKENS: float = 0.60
    REASONING_SAVINGS_RATIO: float = 0.65   # ~65% token savings using 'minimal' reasoning
    CACHE_SAVINGS_RATIO: float = 0.50       # ~50% savings on prompt caching

    # WhatsApp (Stretch)
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
    WHATSAPP_APP_SECRET: str = os.getenv("WHATSAPP_APP_SECRET", "")

    # Database Path
    DB_PATH: str = os.getenv("DB_PATH", str(BASE_DIR / "data" / "satyahd.db"))

    def safe_dict(self) -> dict:
        """Returns settings dictionary with sensitive keys redacted."""
        return {
            "META_API_BASE": self.META_API_BASE,
            "MODEL_NAME": self.MODEL_NAME,
            "WONDER_MODEL": self.WONDER_MODEL,
            "IMAGE_MODEL": self.IMAGE_MODEL,
            "SAM_MODEL": self.SAM_MODEL,
            "AGENT_B_BASE": self.AGENT_B_BASE or None,
            "AGENT_B_MODEL": self.AGENT_B_MODEL or None,
            "ALLOW_MOCK": self.ALLOW_MOCK,
            "DEMO_TODAY": self.DEMO_TODAY,
            "MODEL_TIMEOUT_SECONDS": self.MODEL_TIMEOUT_SECONDS,
            "SIGNING_KEY_PATH": self.SIGNING_KEY_PATH,
            "ANCHOR_DIR": self.ANCHOR_DIR,
            "DB_PATH": self.DB_PATH,
        }


# Global singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    return settings
