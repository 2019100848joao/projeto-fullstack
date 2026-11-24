from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Web Backend"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-this-secret-key"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    run_migrations_on_startup: bool = True
    database_url: str = (
        "postgresql+psycopg://clinic_user:clinic_password@localhost:5432/clinic_db"
    )
    seed_admin_on_startup: bool = True
    seed_admin_email: str = "admin@clinic.com"
    seed_admin_password: str = "Admin123!"
    seed_admin_full_name: str = "Clinic Administrator"

    @property
    def migration_database_url(self) -> str:
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
