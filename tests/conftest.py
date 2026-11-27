import os
from collections.abc import Generator

import pytest

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None]:
    yield
    app.dependency_overrides.clear()
