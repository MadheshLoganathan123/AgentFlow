from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Authoritative application settings loaded from environment or .env file."""
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "AgentFlow API"
    environment: str = "development"
    debug: bool = True
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: List[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"])

    database_url: str = "postgresql+asyncpg://agentflow:agentflow_dev_password@localhost:5432/agentflow"
    database_url_sync: str = "postgresql+psycopg2://agentflow:agentflow_dev_password@localhost:5432/agentflow"

    langgraph_checkpoint_saver: str = "memory"
    max_upload_size_mb: int = 15
    local_storage_path: str = "./uploads"

    # Open Source Lightweight LLM Configuration (Option 1)
    llm_provider: str = "ollama"
    openai_api_key: str = "not-needed-for-local"
    openai_api_base: str = "http://localhost:11434/v1"
    llm_model_name: str = "llama3.2:1b"
    embedding_model_name: str = "all-minilm"


settings = Settings()

