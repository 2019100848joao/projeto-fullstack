import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.models import User, UserDocument


def override_current_user() -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="doctor@example.com",
        full_name="Dr. Example",
        document=UserDocument(
            id="01K4SRY37DGE7K5YWWKNB0DOC1",
            user_id="01K4SRY37DGE7K5YWWKNB0RESW",
            value="CRM-123456",
            type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
        ),
        hashed_password="not-returned",
        role="doctor",
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_me_returns_current_user() -> None:
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        client = TestClient(app)
        response = client.get("/auth/me")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "id": "01K4SRY37DGE7K5YWWKNB0RESW",
        "email": "doctor@example.com",
        "full_name": "Dr. Example",
        "role": "doctor",
        "document": {
            "id": "01K4SRY37DGE7K5YWWKNB0DOC1",
            "user_id": "01K4SRY37DGE7K5YWWKNB0RESW",
            "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
            "value": "CRM-123456",
        },
        "is_active": True,
        "created_at": "2026-09-09T00:00:00Z",
    }


def test_me_requires_authentication() -> None:
    client = TestClient(app)

    response = client.get("/auth/me")

    assert response.status_code == 401
