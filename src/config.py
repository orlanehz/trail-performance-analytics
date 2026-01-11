"""App configuration loaded from environment variables."""

from dataclasses import dataclass
import os

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional dependency
    load_dotenv = None

if load_dotenv:
    load_dotenv()


@dataclass(frozen=True)
class Settings:
    strava_client_id: str | None
    strava_client_secret: str | None
    garmin_api_key: str | None
    app_secret_key: str | None
    data_dir: str


def get_settings() -> Settings:
    return Settings(
        strava_client_id=os.getenv("STRAVA_CLIENT_ID"),
        strava_client_secret=os.getenv("STRAVA_CLIENT_SECRET"),
        garmin_api_key=os.getenv("GARMIN_API_KEY"),
        app_secret_key=os.getenv("APP_SECRET_KEY"),
        data_dir=os.getenv("DATA_DIR", "data"),
    )
