from typing import Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_APP_ENV = "development"
LOCAL_SEED_ADMIN_EMAIL = "admin@clinic.com"
LOCAL_SEED_ADMIN_PASSWORD = "Admin123!"


class Settings(BaseSettings):
    app_name: str = "Web Backend"
    app_env: str = "development"
    debug: bool = False
    timezone: str = "America/Sao_Paulo"
    secret_key: str = "change-this-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    run_migrations_on_startup: bool = True
    database_url: str = (
        "postgresql+psycopg://clinic_user:clinic_password@localhost:5432/clinic_db"
    )
    seed_admin_on_startup: bool = True
    # Outside the local environment these must be set explicitly, otherwise
    # the base admin seed is skipped (no well-known credentials in prod).
    seed_admin_email: str | None = None
    seed_admin_password: str | None = None
    seed_admin_full_name: str = "Clinic Administrator"

    @model_validator(mode="after")
    def apply_local_seed_admin_defaults(self) -> Self:
        if self.app_env == LOCAL_APP_ENV:
            self.seed_admin_email = self.seed_admin_email or LOCAL_SEED_ADMIN_EMAIL
            self.seed_admin_password = (
                self.seed_admin_password or LOCAL_SEED_ADMIN_PASSWORD
            )
        return self

    @property
    def migration_database_url(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
