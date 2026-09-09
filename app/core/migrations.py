from pathlib import Path

from yoyo import get_backend, read_migrations

from app.core.config import settings

MIGRATIONS_PATH = Path(__file__).resolve().parents[2] / "migrations"


def run_migrations() -> None:
    backend = get_backend(settings.migration_database_url)
    migrations = read_migrations(str(MIGRATIONS_PATH))

    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
