import os
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel, Field

# Base project directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env if the file exists (for local development).
# In production containers (e.g. Pterodactyl), variables are passed directly via os.environ.
env_file = BASE_DIR / ".env"
if env_file.is_file():
    load_dotenv(env_file)


def _resolve_db_path() -> Path:
    raw_path = os.getenv("DATABASE_PATH", "data/processed/uzex.db")
    if os.path.isabs(raw_path) or raw_path.startswith("/") or raw_path.startswith("\\"):
        return Path(raw_path)
    return BASE_DIR / Path(raw_path)


def _resolve_raw_dir() -> Path:
    raw_path = os.getenv("RAW_DATA_DIR", "data/raw/uzex_spot_data")
    if os.path.isabs(raw_path) or raw_path.startswith("/") or raw_path.startswith("\\"):
        return Path(raw_path)
    return BASE_DIR / Path(raw_path)


class Settings(BaseModel):
    # Telegram Bot
    BOT_TOKEN: str = Field(default_factory=lambda: os.getenv("BOT_TOKEN", "").strip())

    # Gemini & LLM Settings
    GEMINI_MODEL: str = Field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", os.getenv("LLM_MODEL", "gemini-2.5-flash")).strip()
    )
    GEMINI_API_KEY: str = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY", os.getenv("LLM_API_KEY", "")).strip()
    )
    LLM_PROVIDER: str = Field(default_factory=lambda: os.getenv("LLM_PROVIDER", "gemini").strip())
    LLM_API_KEY: str = Field(default_factory=lambda: os.getenv("LLM_API_KEY", "").strip())
    LLM_MODEL: str = Field(default_factory=lambda: os.getenv("LLM_MODEL", "gemini-2.5-flash").strip())
    LLM_BASE_URL: str = Field(
        default_factory=lambda: os.getenv("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/").strip()
    )
    LLM_TEMPERATURE: float = Field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.0")))

    # Database
    DATABASE_PATH: Path = Field(default_factory=_resolve_db_path)
    RAW_DATA_DIR: Path = Field(default_factory=_resolve_raw_dir)

    # Timeouts
    QUERY_TIMEOUT_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("QUERY_TIMEOUT_SECONDS", "30"))
    )
    MAX_RESPONSE_TIME_SECONDS: int = Field(
        default_factory=lambda: int(os.getenv("MAX_RESPONSE_TIME_SECONDS", "85"))
    )


settings = Settings()
