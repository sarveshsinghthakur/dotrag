import os
from pathlib import Path
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Mistral / NVIDIA
    MISTRAL_API_KEY: str = ""
    MISTRAL_BASE_URL: str = "https://api.mistral.ai/v1"
    MISTRAL_CHAT_MODEL: str = "mistral-small-latest"
    MISTRAL_EMBEDDING_MODEL: str = "mistral-embed"

    # Database
    DATABASE_URL: str = "postgresql://dotrag:dotrag@localhost:5432/dotrag"

    # Qdrant
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000
    FRONTEND_URL: str = "http://localhost:5173"

    # RAG
    CHUNK_SIZE: int = 1024
    CHUNK_OVERLAP: int = 256
    RETRIEVAL_TOP_K: int = 8
    RERANK_TOP_K: int = 5

    # Upload
    MAX_UPLOAD_SIZE_MB: int = 100
    OCR_ENABLED: bool = True

    # Paths
    UPLOAD_DIR: Path = Path("uploads")
    TEMP_DIR: Path = Path("temp")

    model_config = {"env_file": str(Path(__file__).resolve().parent.parent.parent / ".env"), "env_file_encoding": "utf-8"}

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

# Ensure directories exist
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
