import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_auth_service, get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User


def make_user(role: UserRole) -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="user@example.com",
        full_name="Example",
        hashed_password="not-returned",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


class FakeAuthService:
    def __init__(self) -> None:
        self.role: UserRole | None = None

    def list_users(self, *, role: UserRole | None = None) -> list[User]:
        self.role = role
        return [make_user(UserRole.PATIENT)]


def list_users_as(role: UserRole, query: str = "") -> tuple[int, FakeAuthService]:
    service = FakeAuthService()
    app.dependency_overrides[get_current_user] = lambda: make_user(role)
    app.dependency_overrides[get_auth_service] = lambda: service

    try:
        response = TestClient(app).get(f"/auth/users{query}")
    finally:
        app.dependency_overrides.clear()

    return response.status_code, service


@pytest.mark.parametrize(
    "role",
    [UserRole.ADMIN, UserRole.DOCTOR, UserRole.ATTENDANT],
)
def test_staff_can_list_users(role: UserRole) -> None:
    status_code, service = list_users_as(role, "?role=patient")

    assert status_code == 200
    assert service.role == UserRole.PATIENT


def test_patient_cannot_list_users() -> None:
    status_code, _ = list_users_as(UserRole.PATIENT)

    assert status_code == 403


def test_list_users_rejects_unknown_role() -> None:
    status_code, _ = list_users_as(UserRole.ADMIN, "?role=unknown")

    assert status_code == 422


def test_list_users_does_not_return_password() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.ADMIN)
    app.dependency_overrides[get_auth_service] = FakeAuthService

    try:
        response = TestClient(app).get("/auth/users")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "hashed_password" not in response.json()[0]


def test_list_users_requires_authentication() -> None:
    assert TestClient(app).get("/auth/users").status_code == 401
