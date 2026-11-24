import os
from datetime import UTC, datetime

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.core.config import settings
from app.core.security import create_access_token
from app.main import app
from app.modules.auth.dependencies import (
    get_auth_service,
    get_current_user,
)
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


def _make_user(
    role: UserRole = UserRole.PATIENT,
    *,
    is_active: bool = True,
    user_id: str = "01K4SRY37DGE7K5YWWKNB0RESW",
) -> User:
    return User(
        id=user_id,
        email=f"{role.value}@clinic.com",
        full_name=f"User {role.value}",
        hashed_password="hashed-password",
        role=role.value,
        is_active=is_active,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


class StubAuthService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.last_role_filter: UserRole | None = None

    def register(self, user_create: UserCreate) -> User:
        if self.error is not None:
            raise self.error
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password="hashed-password",
            role=UserRole.PATIENT.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def login(self, *, email: str, password: str) -> Token:
        if self.error is not None:
            raise self.error
        return Token(access_token="stub-token")

    def list_users(self, *, role: UserRole | None = None) -> list[User]:
        self.last_role_filter = role
        return [_make_user(role or UserRole.PATIENT)]

    def update_user_role(
        self,
        *,
        current_user: User,
        target_user_id: str,
        new_role: UserRole,
    ) -> User:
        if self.error is not None:
            raise self.error
        return _make_user(new_role, user_id=target_user_id)


def test_register_route_creates_patient_and_rejects_invalid_inputs() -> None:
    app.dependency_overrides[get_auth_service] = lambda: StubAuthService()
    try:
        client = TestClient(app)
        resp = client.post(
            "/auth/register",
            json={
                "email": "novo@clinic.com",
                "full_name": "Novo Paciente",
                "password": "password123",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "patient"

        for invalid_role in ("doctor", "attendant", "admin"):
            bad_role = client.post(
                "/auth/register",
                json={
                    "email": "novo@clinic.com",
                    "full_name": "Novo",
                    "password": "password123",
                    "role": invalid_role,
                },
            )
            assert bad_role.status_code == 422

        short_pwd = client.post(
            "/auth/register",
            json={
                "email": "novo@clinic.com",
                "full_name": "Novo",
                "password": "short",
            },
        )
        assert short_pwd.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_register_route_returns_409_on_duplicate_email() -> None:
    app.dependency_overrides[get_auth_service] = lambda: StubAuthService(
        error=EmailAlreadyRegisteredError()
    )
    try:
        client = TestClient(app)
        resp = client.post(
            "/auth/register",
            json={
                "email": "dup@clinic.com",
                "full_name": "Duplicado",
                "password": "password123",
            },
        )
        assert resp.status_code == 409
    finally:
        app.dependency_overrides.clear()


def test_login_route_maps_invalid_credentials_and_inactive_user() -> None:
    client = TestClient(app)
    try:
        app.dependency_overrides[get_auth_service] = lambda: StubAuthService(
            error=InvalidCredentialsError()
        )
        r_invalid = client.post(
            "/auth/login",
            json={"email": "u@clinic.com", "password": "wrong"},
        )
        assert r_invalid.status_code == 401

        app.dependency_overrides[get_auth_service] = lambda: StubAuthService(
            error=InactiveUserError()
        )
        r_inactive = client.post(
            "/auth/login",
            json={"email": "u@clinic.com", "password": "password123"},
        )
        assert r_inactive.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "non_admin_role",
    [UserRole.PATIENT, UserRole.DOCTOR, UserRole.ATTENDANT],
)
def test_list_users_route_allows_only_admin(non_admin_role: UserRole) -> None:
    stub = StubAuthService()
    client = TestClient(app)
    assert client.get("/auth/users").status_code == 401

    app.dependency_overrides[get_auth_service] = lambda: stub
    try:
        app.dependency_overrides[get_current_user] = lambda: _make_user(non_admin_role)
        assert client.get("/auth/users").status_code == 403

        app.dependency_overrides[get_current_user] = lambda: _make_user(UserRole.ADMIN)
        ok = client.get("/auth/users", params={"role": "patient"})
        assert ok.status_code == 200
        assert stub.last_role_filter == UserRole.PATIENT
        assert ok.json()[0]["role"] == "patient"
    finally:
        app.dependency_overrides.clear()


def test_update_user_role_route_maps_success_404_and_403() -> None:
    client = TestClient(app)
    assert (
        client.patch("/auth/users/01USER/role", json={"role": "doctor"}).status_code
        == 401
    )

    app.dependency_overrides[get_current_user] = lambda: _make_user(UserRole.ADMIN)
    try:
        app.dependency_overrides[get_auth_service] = lambda: StubAuthService()
        ok = client.patch("/auth/users/01USER/role", json={"role": "doctor"})
        assert ok.status_code == 200
        assert ok.json()["role"] == "doctor"

        app.dependency_overrides[get_auth_service] = lambda: StubAuthService(
            error=UserNotFoundError()
        )
        assert (
            client.patch("/auth/users/01USER/role", json={"role": "doctor"}).status_code
            == 404
        )

        app.dependency_overrides[get_auth_service] = lambda: StubAuthService(
            error=RoleChangeNotAllowedError()
        )
        assert (
            client.patch("/auth/users/01USER/role", json={"role": "doctor"}).status_code
            == 403
        )
    finally:
        app.dependency_overrides.clear()


def test_get_current_user_validates_jwt_and_active_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(HTTPException) as exc_none:
        get_current_user(credentials=None, db=object())  # type: ignore[arg-type]
    assert exc_none.value.status_code == 401

    bad_creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials="invalid.jwt.token",
    )
    with pytest.raises(HTTPException) as exc_bad:
        get_current_user(credentials=bad_creds, db=object())  # type: ignore[arg-type]
    assert exc_bad.value.status_code == 401

    no_sub_token = jwt.encode(
        {"foo": "bar"},
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    no_sub_creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=no_sub_token,
    )
    with pytest.raises(HTTPException) as exc_nosub:
        get_current_user(credentials=no_sub_creds, db=object())  # type: ignore[arg-type]
    assert exc_nosub.value.status_code == 401

    valid_token = create_access_token("01USER")
    valid_creds = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=valid_token,
    )

    monkeypatch.setattr(
        "app.modules.auth.dependencies.UserRepository.get_by_id",
        lambda self, uid: None,
    )
    with pytest.raises(HTTPException) as exc_missing:
        get_current_user(credentials=valid_creds, db=object())  # type: ignore[arg-type]
    assert exc_missing.value.status_code == 401

    monkeypatch.setattr(
        "app.modules.auth.dependencies.UserRepository.get_by_id",
        lambda self, uid: _make_user(UserRole.PATIENT, is_active=False),
    )
    with pytest.raises(HTTPException) as exc_inactive:
        get_current_user(credentials=valid_creds, db=object())  # type: ignore[arg-type]
    assert exc_inactive.value.status_code == 403
