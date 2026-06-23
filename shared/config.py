from pydantic_settings import BaseSettings
from pydantic import field_validator
from functools import lru_cache
import logging

log = logging.getLogger(__name__)


class Settings(BaseSettings):
    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "oncology_intel"
    postgres_user: str = "oncology"
    postgres_password: str = ""

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # Elasticsearch
    elasticsearch_url: str = "http://elasticsearch:9200"

    # Redis
    redis_url: str = "redis://redis:6379"

    # Temporal
    temporal_host: str = "temporal:7233"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_model_sonnet: str = "claude-sonnet-4-6"
    anthropic_model_haiku: str = "claude-haiku-4-5-20251001"

    # Voyage AI (separate from Anthropic)
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3"
    voyage_embedding_dims: int = 1024

    # External APIs
    ncbi_api_key: str = ""
    ncbi_email: str = ""
    semantic_scholar_api_key: str = ""
    core_api_key: str = ""
    linkedin_api_key: str = ""
    wiley_api_key: str = ""
    apollo_api_key: str = ""
    twitter_bearer_token: str = ""

    # CORS
    allowed_origins: list[str] = ["http://localhost:3000", "http://localhost"]

    @field_validator("postgres_password", "neo4j_password", mode="after")
    @classmethod
    def warn_default_password(cls, v: str, info: object) -> str:
        if v in ("changeme", "password", "secret", ""):
            log.warning(
                "Insecure or missing password for field. Set it in .env before deploying."
            )
        return v

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "case_sensitive": False}


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
