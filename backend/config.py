"""Application settings, loaded from the environment and the repo-root .env."""
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    deepseek_api_key: str = Field(
        default="", validation_alias=AliasChoices("DEEPSEEK_API_KEY", "API_KEY")
    )
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")
    deepseek_base_url: str = Field(
        default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL"
    )
    llm_timeout_s: float = Field(default=60.0, validation_alias="LLM_TIMEOUT_S")
    llm_max_retries: int = Field(default=2, validation_alias="LLM_MAX_RETRIES")

    # Initial value only: the UI toggle persists an override in the AppSetting table.
    demo_mode: bool = Field(default=False, validation_alias="DEMO_MODE")
    demo_step_delay_ms: int = Field(default=500, validation_alias="DEMO_STEP_DELAY_MS")

    data_dir: Path = Field(default=ROOT / "data", validation_alias="DATA_DIR")
    database_url: str = Field(default="", validation_alias="DATABASE_URL")
    cors_origins: str = Field(default="http://localhost:3010", validation_alias="CORS_ORIGINS")

    # USD per 1M tokens; override when DeepSeek changes its price list.
    deepseek_input_usd_per_m: float = Field(default=0.27, validation_alias="DEEPSEEK_INPUT_USD_PER_M")
    deepseek_output_usd_per_m: float = Field(default=1.10, validation_alias="DEEPSEEK_OUTPUT_USD_PER_M")

    @property
    def seed_dir(self) -> Path:
        return ROOT / "data" / "seed"

    @property
    def workspace_dir(self) -> Path:
        return self.data_dir / "workspace"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def db_url(self) -> str:
        return self.database_url or f"sqlite:///{self.data_dir / 'tenderscout.db'}"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
