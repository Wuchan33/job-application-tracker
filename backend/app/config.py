from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    llm_provider: Literal["gemini", "ollama"] = "ollama"
    ollama_model: str = "qwen2.5:14b"
    gemini_models: str = "gemini-3.1-flash-lite,gemini-3.5-flash-lite"
    gemini_api_key: str | None = None
    database_url: str

    @property
    def gemini_model_list(self) -> list[str]:
        return [m.strip() for m in self.gemini_models.split(",") if m.strip()]


settings = Settings()
