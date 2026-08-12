from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), str(_LOCAL_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # When True (default — no GCP project/credentials are available yet),
    # every service computes a genuine local equivalent (statsmodels /
    # scikit-learn) against the in-process synthetic dataset instead of
    # querying BigQuery. When False, services run real BigQuery ML SQL via
    # bigquery/client.py. There is deliberately no silent fallback from
    # False to True: if DEMO_MODE=false but BigQuery isn't actually reachable,
    # the app fails at startup rather than quietly serving demo numbers
    # under a "bigquery" label (see bigquery/client.py).
    demo_mode: bool = True

    gcp_project_id: str | None = None
    bq_location: str = "asia-northeast1"
    google_application_credentials: str | None = None

    cors_origins: str = "http://localhost:3030"

    # Synthetic dataset generation (see data/synth.py)
    synth_seed: int = 42

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
