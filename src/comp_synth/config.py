from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """CompSynth 全局配置，从环境变量和 .env 文件加载"""

    model_config = SettingsConfigDict(
        env_prefix='COMPSYNTH_',
        env_file='.env',
        extra="ignore"
    )

    # 路径
    log_dir: Path = Path("./logs")
    data_dir: Path = Path("./data")

    # LLM
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    model: str = "gpt-4o-mini"

    # 存储
    crawl_db_path: Path = Path("./data/crawl_state.db")
    site_schema_db_path: Path = Path("./data/site_schemas.db")

    # 爬虫
    request_timeout: int = 30
    max_concurrent_requests: int = 5
    list_page_time_threshold_days: int = 7
    list_page_count_threshold: int = 20
    selector_zero_refresh_enabled: bool = True
    selector_zero_refresh_days: int = 3
    selector_zero_refresh_lookback_days: int = 7
    selector_zero_refresh_cooldown_hours: int = 24

    # 订阅与输出
    subscriptions_path: Path = Path("./subscriptions.yaml")
    output_dir: Path = Path("./output")


settings = Settings()

# 兼容日志模块: from comp_synth import config; config.LOG_DIR
LOG_DIR = str(settings.log_dir)


def apply_db_overrides(overrides: dict[str, str]) -> None:
    """Patch the settings singleton from DB overrides on startup."""
    for key, value in overrides.items():
        if not hasattr(settings, key):
            continue
        field_type = type(getattr(settings, key))
        try:
            if field_type is Path:
                setattr(settings, key, Path(value))
            elif field_type is bool:
                setattr(settings, key, value.lower() in ("true", "1", "yes"))
            elif field_type is int:
                setattr(settings, key, int(value))
            else:
                setattr(settings, key, value)
        except (ValueError, TypeError):
            from loguru import logger
            logger.warning("Skipping invalid override {key}={value}", key=key, value=value)
