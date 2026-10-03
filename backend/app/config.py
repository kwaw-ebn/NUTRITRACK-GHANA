from functools import lru_cache
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./nutritrack.db"
    jwt_secret: str = "development-only-change-this-secret-32-characters"
    setup_token: str = ""
    main_admin_email: str = ""
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    access_minutes: int = Field(default=15, ge=1, le=60)
    refresh_days: int = Field(default=7, ge=1, le=30)
    app_version: str = "0.1.0"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    frontend_url: str = "http://localhost:5173"

    @model_validator(mode="after")
    def production(self):
        if self.environment == "production":
            if len(self.jwt_secret) < 32 or self.jwt_secret.startswith("development"):
                raise ValueError("Production requires a strong JWT_SECRET")
            if len(self.setup_token) < 32:
                raise ValueError("Production requires a strong SETUP_TOKEN")
            if not self.database_url.startswith(("postgresql", "postgres")):
                raise ValueError("Production requires PostgreSQL")
            if any(not origin.startswith("https://") for origin in self.cors_origins.split(",")):
                raise ValueError("Production CORS origins must use HTTPS")
        return self


@lru_cache
def settings():
    return Settings()
