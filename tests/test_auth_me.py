import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.document_types.models import DocumentType
from app.modules.users.models import User, UserDocument


def override_current_user() -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="doctor@example.com",
        full_name="Dr. Example",
        documents=[
            UserDocument(
                id="01K4SRY37DGE7K5YWWKNB0DOC1",
                user_id="01K4SRY37DGE7K5YWWKNB0RESW",
                value="CRM-123456",
                type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                document_type=DocumentType(
                    id="01K4SRY37DGE7K5YWWKNB0TYPE", type="CRM"
                ),
            ),
            UserDocument(
                id="01K4SRY37DGE7K5YWWKNB0DOC2",
                user_id="01K4SRY37DGE7K5YWWKNB0RESW",
                value="123.456.789-00",
                type_id="01K4SRY37DGE7K5YWWKNB0TYP2",
                document_type=DocumentType(
                    id="01K4SRY37DGE7K5YWWKNB0TYP2", type="CPF"
                ),
            ),
        ],
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
        "documents": [
            {
                "id": "01K4SRY37DGE7K5YWWKNB0DOC1",
                "user_id": "01K4SRY37DGE7K5YWWKNB0RESW",
                "value": "CRM-123456",
                "document_type": {
                    "id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "type": "CRM",
                },
            },
            {
                "id": "01K4SRY37DGE7K5YWWKNB0DOC2",
                "user_id": "01K4SRY37DGE7K5YWWKNB0RESW",
                "value": "123.456.789-00",
                "document_type": {
                    "id": "01K4SRY37DGE7K5YWWKNB0TYP2",
                    "type": "CPF",
                },
            },
        ],
        "is_active": True,
        "created_at": "2026-09-09T00:00:00Z",
    }


def test_me_requires_authentication() -> None:
    client = TestClient(app)

    response = client.get("/auth/me")

    assert response.status_code == 401
