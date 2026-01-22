from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Odds Vision"
    database_url: str = Field(default="sqlite:///./odds_vision.db")
    odds_api_key: str = Field(default="")
    odds_api_base_url: str = Field(default="https://api.the-odds-api.com")
    odds_api_sport_key: str = Field(default="basketball_nba")
    timezone: str = Field(default="America/Bahia")
    ev_threshold: float = Field(default=0.03)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
