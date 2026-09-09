import os

from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_auth_service
from app.modules.auth.schemas import Token


class FakeAuthService:
    def login(self, *, email: str, password: str) -> Token:
        assert email == "doctor@example.com"
        assert password == "password123"
        return Token(access_token="fake-token")


def override_auth_service() -> FakeAuthService:
    return FakeAuthService()


def test_login_uses_json_body() -> None:
    app.dependency_overrides[get_auth_service] = override_auth_service

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/login",
            json={
                "email": "doctor@example.com",
                "password": "password123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "access_token": "fake-token",
        "token_type": "bearer",
    }
