from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Odds Vision"
    database_url: str = Field(default="sqlite:///./odds_vision.db")
    odds_api_key: str = Field(default="")
    odds_api_base_url: str = Field(default="https://api.the-odds-api.com")
    odds_api_sport_key: str = Field(default="basketball_nba")
    odds_api_regions: str = Field(default="us")
    odds_api_markets: str = Field(default="totals,alternate_totals")
    odds_api_odds_format: str = Field(default="decimal")
    odds_api_date_format: str = Field(default="iso")
    sportsdataio_api_key: str = Field(default="")
    sportsdataio_base: str = Field(default="https://api.sportsdata.io/v3/nba")
    sportsdataio_subscription_header: str = Field(
        default="Ocp-Apim-Subscription-Key"
    )
    timezone: str = Field(default="America/Bahia")
    ev_threshold: float = Field(default=0.03)
    blend_market_weight: float = Field(default=0.7)
    blend_model_weight: float = Field(default=0.3)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    return Settings()
