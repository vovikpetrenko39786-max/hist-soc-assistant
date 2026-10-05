from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "History & Social Studies Teacher Assistant"
    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://teacher:teacher@localhost:5432/teacher_assistant"
    auto_create_tables: bool = True
    source_storage_dir: str = "data/source_files"

    # Embeddings.
    # "hash" is deterministic and offline, intended for development/tests.
    # "http" calls a compatible /embeddings endpoint configured below.
    embedding_provider: str = "hash"
    embedding_model: str = "hash-384-v1"
    embedding_dim: int = 384
    embedding_batch_size: int = 64
    embedding_http_base_url: str | None = None
    embedding_http_api_key: str | None = None
    embedding_http_model: str | None = None
    embedding_http_timeout_seconds: float = 60.0

    # Retrieval defaults.
    retrieval_candidate_k: int = 40
    retrieval_top_k: int = 8
    retrieval_language_config: str = "russian"

    # Grounded generation.
    # "template" is deterministic and offline for tests/demo.
    # "http" calls a compatible chat-completions-style endpoint.
    generation_provider: str = "template"
    generation_model: str = "template-lesson-v1"
    generation_http_base_url: str | None = None
    generation_http_api_key: str | None = None
    generation_http_model: str | None = None
    generation_http_timeout_seconds: float = 90.0
    generation_temperature: float = 0.2

    # Production output layer.
    output_storage_dir: str = "data/generated_outputs"
    output_template: str = "school_clean"
    output_font_name: str = "Liberation Sans"
    output_keep_intermediate_docx_for_pdf: bool = True
    libreoffice_binary: str = "soffice"

    # Controlled web fallback (OpenAI Responses API).
    openai_api_key: str | None = None
    openai_responses_base_url: str = "https://api.openai.com/v1"
    web_search_provider: str = "openai"
    web_search_model: str = "gpt-5.5"
    web_search_context_size: str = "low"
    web_search_timeout_seconds: float = 90.0
    web_fallback_min_local_hits: int = 2
    web_allow_general_after_official: bool = True
    web_max_sources: int = 12

    # OpenAI Responses generation for production/pilot.
    openai_generation_model: str = "gpt-5.6-terra"
    openai_generation_reasoning_effort: str = "medium"
    openai_generation_timeout_seconds: float = 120.0
    openai_generation_max_retries: int = 1

    # Pilot / admin.
    pilot_release_label: str = "1.0-beta"
    admin_api_key: str | None = None

    # Telegram adapter.
    telegram_bot_token: str | None = None
    telegram_backend_base_url: str = "http://127.0.0.1:8000"
    telegram_request_timeout_seconds: float = 240.0
    telegram_default_formats: str = "docx"
    telegram_admin_ids: str = ""
    telegram_beta_notice: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
