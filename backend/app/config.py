from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/aspredictive")
    secret_key: str = os.getenv("SECRET_KEY", "change-this-secret-key")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    model_version: str = os.getenv("MODEL_VERSION", "1.0.0")


settings = Settings()
