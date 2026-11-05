import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Load environment variables from .env if present
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings(BaseModel):
    # Telegram Bot
    BOT_TOKEN: str = Field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))

    # Gemini & LLM Settings
    GEMINI_MODEL: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash"))
    )
    GEMINI_API_KEY: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("LLM_API_KEY", ""))
    )
    LLM_PROVIDER: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini"))
    LLM_API_KEY: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", ""))
    LLM_MODEL: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.5-flash"))
    LLM_BASE_URL: str = Field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    )
    LLM_TEMPERATURE: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))

    # Database
    DATABASE_PATH: Path = Field(
        default_factory=lambda: BASE_DIR / Path(os.getenv("DATABASE_PATH", "data/processed/uzex.db"))
    )
    RAW_DATA_DIR: Path = Field(
        default_factory=lambda: BASE_DIR / Path(os.getenv("RAW_DATA_DIR", "data/raw/uzex_spot_data"))
    )

    # Timeouts
    QUERY_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    )
    MAX_RESPONSE_TIME_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RESPONSE_TIME_SECONDS", "85"))
    )


settings = Settings()
