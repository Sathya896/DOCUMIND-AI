"""
Application configuration.

WHY THIS FILE EXISTS
---------------------
Hard-coding values like folder paths, model names, or API URLs directly inside
business logic makes an application brittle: changing an environment (e.g.
moving from a laptop to Render) means hunting through the codebase for magic
strings.

Instead, we centralise every configurable value in one typed `Settings`
object built with `pydantic-settings`. Benefits:

1. Type safety   - `pydantic` validates types (e.g. `CHUNK_SIZE` must be an
   int) at startup, so misconfiguration fails fast and loudly instead of
   causing a confusing bug three layers deep.
2. Single source of truth - every other module imports `settings` instead of
   calling `os.getenv(...)` in twenty different places.
3. Environment overrides - any value can be overridden by an environment
   variable (or a `.env` file) without touching code. This is exactly how
   12-factor apps are configured, and it is what lets the *same* code run
   locally, in CI, and on Render with different values.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# The backend/ directory (two levels up from this file: config/ -> app/ -> backend/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Typed application settings.

    Every field below can be overridden by an environment variable of the
    same name (case-insensitive), or by placing a `.env` file in `backend/`.
    """

    # --- General ---
    APP_NAME: str = "DocuMind AI"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"  # "development" | "production"

    # --- CORS ---
    # Comma-separated list of allowed origins for the frontend. In production
    # this should be the exact Vercel URL, never "*", to avoid exposing the
    # API to arbitrary websites.
    CORS_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- File storage ---
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    VECTORSTORE_DIR: Path = BASE_DIR / "vectorstore"
    DATA_DIR: Path = BASE_DIR / "data"
    MAX_UPLOAD_SIZE_MB: int = 25
    ALLOWED_EXTENSIONS: tuple[str, ...] = (".pdf",)

    # --- Database ---
    # SQLite is file-based, so the "connection string" is just a path on disk.
    # This is perfect for a portfolio project: zero setup, single file, easy
    # to inspect. A real multi-server production system would likely swap
    # this for Postgres, but the SQLAlchemy layer makes that a config change,
    # not a rewrite.
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'data' / 'documind.db'}"

    # --- Chunking ---
    CHUNK_SIZE: int = 1000          # characters per chunk
    CHUNK_OVERLAP: int = 200        # characters shared between consecutive chunks

    # --- Embeddings ---
    EMBEDDING_MODEL_NAME: str = "BAAI/bge-small-en-v1.5"
    EMBEDDING_DIMENSION: int = 384  # bge-small-en-v1.5 produces 384-dim vectors

    # --- Retrieval ---
    TOP_K_RESULTS: int = 4          # how many chunks to retrieve per question

    # --- LLM (Ollama) ---
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:3b"
    OLLAMA_REQUEST_TIMEOUT_SECONDS: float = 120.0

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> list[str]:
        """Split the comma-separated CORS_ORIGINS string into a clean list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def _ensure_runtime_directories(settings: "Settings") -> None:
    """Create the folders the app writes to if they don't exist yet.

    This runs once at import time so that every service can assume these
    directories already exist, instead of every service re-checking.
    """
    for directory in (settings.UPLOAD_DIR, settings.VECTORSTORE_DIR, settings.DATA_DIR):
        directory.mkdir(parents=True, exist_ok=True)


# A module-level singleton. FastAPI route handlers and services import this
# object directly (`from app.config.settings import settings`) rather than
# instantiating `Settings()` themselves, so the whole app shares one config.
settings = Settings()
_ensure_runtime_directories(settings)
