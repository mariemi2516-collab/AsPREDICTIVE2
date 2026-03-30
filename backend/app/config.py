from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost:5432/aspredictive")
    secret_key: str = os.getenv("SECRET_KEY", "change-this-secret-key")
    access_token_expire_minutes: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "720"))
    model_version: str = os.getenv("MODEL_VERSION", "1.0.0")
    allow_self_registration: bool = os.getenv("ALLOW_SELF_REGISTRATION", "false").strip().lower() == "true"
    expose_password_reset_token: bool = os.getenv("EXPOSE_PASSWORD_RESET_TOKEN", "false").strip().lower() == "true"
    initial_admin_email: str | None = os.getenv("INITIAL_ADMIN_EMAIL") or None
    initial_admin_password: str | None = os.getenv("INITIAL_ADMIN_PASSWORD") or None
    initial_admin_name: str = os.getenv("INITIAL_ADMIN_NAME", "Administrador Inicial")
    initial_admin_organization_key: str = os.getenv("INITIAL_ADMIN_ORGANIZATION_KEY", "default").strip() or "default"
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "https://aspredictive.netlify.app,http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]


settings = Settings()
