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
    model: str = "gpt-4o-mini"

    # 存储
    chroma_persist_dir: Path = Path("./data/chroma")
    crawl_db_path: Path = Path("./data/crawl_state.db")
    site_schema_db_path: Path = Path("./data/site_schemas.db")
    vector_ttl_days: int = 30

    # 爬虫
    request_timeout: int = 30
    max_concurrent_requests: int = 5
    rss_lookback_days: int = 7
    list_page_time_threshold_days: int = 7
    list_page_count_threshold: int = 20

    # 订阅与输出
    subscriptions_path: Path = Path("./subscriptions.yaml")
    output_dir: Path = Path("./output")


settings = Settings()

# 兼容日志模块: from comp_synth import config; config.LOG_DIR
LOG_DIR = str(settings.log_dir)
