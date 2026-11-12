from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    litellm_base_url: str = "http://127.0.0.1:4000/v1"
    litellm_api_key: str = "local-dev-key"
    litellm_model: str = "yby-local"
    openrouter_monthly_budget_usd: float = 3.50

    mqtt_host: str = "127.0.0.1"
    mqtt_port: int = 1883
    mqtt_topic_validated: str = "yby/seed/code/validated"
    mqtt_topic_agents_trace: str = "yby/seed/agents/trace"
    mqtt_max_concurrent_jobs: int = 1

    datasets_path: Path = Path("data/datasets/validated_pairs.jsonl")
    models_dir: Path = Path("data/models")

    sandbox_python_image: str = "yby-sandbox-python:3.12"
    sandbox_cpp_image: str = "gcc:13-bookworm"
    sandbox_memory_mb: int = 512
    sandbox_timeout_sec: int = 30

    max_generation_attempts: int = 3

    vast_api_key: str = ""


def get_settings() -> Settings:
    return Settings()
