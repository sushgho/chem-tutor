from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


MATH_ANSWER_VALIDATION_RULES = (
    "For every mathematics problem, show the solution step by step. Clearly "
    "distinguish intermediate calculations from the final answer. Simplify every "
    "fraction to lowest terms using the greatest common divisor, and verify that "
    "the simplified fraction is equivalent to the original. Never leave a "
    "reducible fraction unsimplified. For probability questions, verify that the "
    "final probability is between 0 and 1 inclusive. Put the final answer in a "
    "boxed mathematical format, for example: 24/132600 = 4/22100 = 1/5525, "
    "Final Answer: $\\boxed{1/5525}$."
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://tutor:tutor@localhost:5432/tutor"
    groq_api_key: str = ""
    model: str = "openai/gpt-oss-120b"
    embedding_mode: Literal["sentence-transformers", "keyword"] = "sentence-transformers"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embed_dim: int = 384
    # Cosine distance above which a chunk is treated as irrelevant
    max_dist: float = 0.6
    cors_origins: str = "http://localhost:3000"
    supabase_url: str = ""
    supabase_jwt_secret: str = ""


settings = Settings()
