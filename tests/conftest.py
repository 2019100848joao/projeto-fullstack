import os
from collections.abc import Generator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.core.database import Base  # noqa: E402
from app.main import app  # noqa: E402

# Registers every table on Base.metadata.
from app.modules.appointments.models import Appointment  # noqa: E402, F401
from app.modules.auth.enums import UserRole  # noqa: E402
from app.modules.users.models import User  # noqa: E402


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    # A file database, so two sessions have separate connections, as two
    # concurrent requests would.
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'clinic.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                full_name=user_id,
                hashed_password="hashed",
                role=role.value,
            )
            for user_id, role in (
                ("patient", UserRole.PATIENT),
                ("doctor", UserRole.DOCTOR),
                ("other-doctor", UserRole.DOCTOR),
                ("attendant", UserRole.ATTENDANT),
            )
        )
        db.commit()
    yield engine
    engine.dispose()
