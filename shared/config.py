from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # PostgreSQL
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    postgres_db: str = "oncology_intel"
    postgres_user: str = "oncology"
    postgres_password: str = "changeme"

    # Neo4j
    neo4j_uri: str = "bolt://neo4j:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"

    # Elasticsearch
    elasticsearch_url: str = "http://elasticsearch:9200"

    # Redis
    redis_url: str = "redis://redis:6379"

    # Temporal
    temporal_host: str = "temporal:7233"

    # Anthropic
    anthropic_api_key: str = ""

    # External APIs
    ncbi_api_key: str = ""
    ncbi_email: str = ""
    linkedin_api_key: str = ""
    wiley_api_key: str = ""
    apollo_api_key: str = ""

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
