from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"
_LOCAL_ENV = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(_ROOT_ENV), str(_LOCAL_ENV), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # "demo" (default — no GCP/Snowflake credentials are available yet):
    # every service computes a genuine local equivalent (statsmodels /
    # scikit-learn) against the in-process synthetic dataset. "bigquery" or
    # "snowflake": services run real BigQuery ML SQL / Snowflake Cortex ML
    # Functions + Snowpark ML via bigquery/client.py / snowflake/client.py.
    # There is deliberately no silent fallback to "demo": if execution_mode
    # is "bigquery"/"snowflake" but the target isn't actually reachable, the
    # app fails at startup rather than quietly serving demo numbers under a
    # non-"demo" source label (see bigquery/client.py, snowflake/client.py).
    execution_mode: Literal["demo", "bigquery", "snowflake"] = "demo"

    gcp_project_id: str | None = None
    bq_location: str = "asia-northeast1"
    google_application_credentials: str | None = None

    snowflake_account: str | None = None
    snowflake_user: str | None = None
    snowflake_password: str | None = None
    snowflake_role: str | None = None
    snowflake_warehouse: str = "DATA_ENGINEER_PILOT_WH"
    snowflake_database: str = "DATA_ENGINEER_PILOT"
    # Set when the account's default region doesn't host the requested
    # cortex_model — routes Cortex inference to a region that does.
    snowflake_cortex_cross_region: str | None = None
    cortex_model: str = "llama3.1-70b"

    # Optional enhancement to the DEMO path only (source stays "demo" either
    # way — this never changes which ML backend computed the numbers, only
    # how the narrative ai_insight text is produced). When set, each
    # service's _prepare_demo() attempts to replace its template-generated
    # ai_insight with a real OpenAI completion (ai_insight_generated_by
    # becomes "openai"). Unlike execution_mode=bigquery/snowflake, a failed
    # or missing key does NOT fail the app at startup — the demo path's ML
    # computation is fully correct and functional regardless, so a failed
    # OpenAI call just falls back to the template sentence
    # (ai_insight_generated_by stays "template", never mislabeled "openai").
    # See src/ai/openai_client.py.
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    cors_origins: str = "http://localhost:3030"

    # Synthetic dataset generation (see data/synth.py)
    synth_seed: int = 42

    @property
    def is_demo(self) -> bool:
        return self.execution_mode == "demo"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
