from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class HTTPSettings(BaseModel):
    timeout: float = 30.0
    max_retries: int = 3
    max_retry_delay: float = 5.0


class Settings(BaseSettings):
    http: HTTPSettings

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_nested_delimiter="__"
    )


settings = Settings()