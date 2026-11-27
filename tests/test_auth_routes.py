import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_auth_service, get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import Token, UserCreate


def make_user(
    role: UserRole = UserRole.PATIENT,
    user_id: str = "01K4SRY37DGE7K5YWWKNB0RESW",
) -> User:
    return User(
        id=user_id,
        email="user@example.com",
        full_name="Example User",
        hashed_password="not-returned",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


class FakeAuthService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.role_filter: UserRole | None = None

    def register(self, user_create: UserCreate) -> User:
        if self.error is not None:
            raise self.error
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password="not-returned",
            role=UserRole.PATIENT.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def login(self, *, email: str, password: str) -> Token:
        if self.error is not None:
            raise self.error
        return Token(access_token="fake-token")

    def list_users(self, *, role: UserRole | None = None) -> list[User]:
        self.role_filter = role
        return [make_user(role or UserRole.PATIENT)]

    def update_user_role(
        self,
        *,
        current_user: User,
        target_user_id: str,
        new_role: UserRole,
    ) -> User:
        if self.error is not None:
            raise self.error
        return make_user(new_role, user_id=target_user_id)


def override_auth_service() -> FakeAuthService:
    return FakeAuthService()


def test_register_returns_201_for_patient() -> None:
    app.dependency_overrides[get_auth_service] = override_auth_service

    response = TestClient(app).post(
        "/auth/register",
        json={
            "email": "patient@example.com",
            "full_name": "Patient Example",
            "password": "password123",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "patient"


@pytest.mark.parametrize("role", ["doctor", "attendant", "admin"])
def test_register_rejects_non_patient_roles(role: str) -> None:
    app.dependency_overrides[get_auth_service] = override_auth_service

    response = TestClient(app).post(
        "/auth/register",
        json={
            "email": "user@example.com",
            "full_name": "Example",
            "password": "password123",
            "role": role,
        },
    )

    assert response.status_code == 422


def test_register_returns_409_when_email_exists() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        error=EmailAlreadyRegisteredError()
    )

    response = TestClient(app).post(
        "/auth/register",
        json={
            "email": "patient@example.com",
            "full_name": "Patient Example",
            "password": "password123",
        },
    )

    assert response.status_code == 409


def test_login_returns_401_on_invalid_credentials() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        error=InvalidCredentialsError()
    )

    response = TestClient(app).post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401


def test_login_returns_403_when_user_is_inactive() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        error=InactiveUserError()
    )

    response = TestClient(app).post(
        "/auth/login",
        json={"email": "user@example.com", "password": "password123"},
    )

    assert response.status_code == 403


def test_admin_can_list_users_filtered_by_role() -> None:
    service = FakeAuthService()
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.ADMIN)
    app.dependency_overrides[get_auth_service] = lambda: service

    response = TestClient(app).get("/auth/users?role=patient")

    assert response.status_code == 200
    assert service.role_filter == UserRole.PATIENT
    assert "hashed_password" not in response.json()[0]


@pytest.mark.parametrize(
    "role",
    [UserRole.PATIENT, UserRole.DOCTOR, UserRole.ATTENDANT],
)
def test_non_admin_cannot_list_users(role: UserRole) -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(role)
    app.dependency_overrides[get_auth_service] = override_auth_service

    response = TestClient(app).get("/auth/users")

    assert response.status_code == 403


def test_list_users_requires_authentication() -> None:
    response = TestClient(app).get("/auth/users")

    assert response.status_code == 401


def test_update_user_role_returns_200() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.ADMIN)
    app.dependency_overrides[get_auth_service] = override_auth_service

    response = TestClient(app).patch(
        "/auth/users/01K4SRY37DGE7K5YWWKNB0RESW/role",
        json={"role": "doctor"},
    )

    assert response.status_code == 200
    assert response.json()["role"] == "doctor"


def test_update_user_role_returns_404_when_user_not_found() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.ADMIN)
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        error=UserNotFoundError()
    )

    response = TestClient(app).patch(
        "/auth/users/01K4SRY37DGE7K5YWWKNB0RESW/role",
        json={"role": "doctor"},
    )

    assert response.status_code == 404


def test_update_user_role_returns_403_when_not_allowed() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.PATIENT)
    app.dependency_overrides[get_auth_service] = lambda: FakeAuthService(
        error=RoleChangeNotAllowedError()
    )

    response = TestClient(app).patch(
        "/auth/users/01K4SRY37DGE7K5YWWKNB0RESW/role",
        json={"role": "doctor"},
    )

    assert response.status_code == 403
