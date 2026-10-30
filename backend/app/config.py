import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "UK Day-Ahead Wind Power Trading API"
    API_PREFIX: str = "/api"
    ELEXON_BASE_URL: str = "https://data.elexon.co.uk/bmrs/api/v1"
    DATA_DIR: str = os.getenv("DATA_DIR", os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data")))
    DEFAULT_CUTOFF: str = "09:00"
    DEFAULT_TZ: str = "Europe/London"
    
    # Validation boundary
    JANUARY_START: str = "2026-01-01"
    JANUARY_END: str = "2026-01-31"

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

settings = Settings()
