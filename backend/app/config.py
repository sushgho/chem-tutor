from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://tutor:tutor@localhost:5432/tutor"
    anthropic_api_key: str = ""
    model: str = "claude-sonnet-5-5"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    # Cosine distance above which a chunk is treated as irrelevant
    max_dist: float = 0.6
    cors_origins: str = "http://localhost:3000"


settings = Settings()
