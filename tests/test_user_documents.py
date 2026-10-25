import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import inspect

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_auth_service, get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    DocumentAlreadyExistsError,
    DocumentTypeNotFoundError,
)
from app.modules.auth.models import DocumentType, User, UserDocument
from app.modules.auth.schemas import (
    DocumentTypeCreate,
    UserCreate,
    UserDocumentCreate,
)


class FakeDocumentAuthService:
    def __init__(
        self,
        *,
        missing_type: bool = False,
        already_exists: bool = False,
    ) -> None:
        self.missing_type = missing_type
        self.already_exists = already_exists

    def register(self, user_create: UserCreate) -> User:
        if self.missing_type:
            raise DocumentTypeNotFoundError

        doc = (
            UserDocument(
                id="01K4SRY37DGE7K5YWWKNB0DOC1",
                user_id="01K4SRY37DGE7K5YWWKNB0RESW",
                type_id=user_create.document.type_id,
                value=user_create.document.value,
            )
            if user_create.document is not None
            else None
        )
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=user_create.email,
            full_name=user_create.full_name,
            document=doc,
            hashed_password="hashed-password",
            role=user_create.role.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def create_document_type(
        self,
        doc_type_create: DocumentTypeCreate,
    ) -> DocumentType:
        return DocumentType(
            id="01K4SRY37DGE7K5YWWKNB0TYPE",
            type=doc_type_create.type,
        )

    def create_user_document(
        self,
        *,
        current_user: User,
        doc_create: UserDocumentCreate,
    ) -> UserDocument:
        if self.missing_type:
            raise DocumentTypeNotFoundError
        if self.already_exists:
            raise DocumentAlreadyExistsError
        return UserDocument(
            id="01K4SRY37DGE7K5YWWKNB0DOC1",
            user_id=current_user.id,
            type_id=doc_create.type_id,
            value=doc_create.value,
        )


def override_current_user() -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="patient@example.com",
        full_name="Patient Example",
        hashed_password="not-returned",
        role=UserRole.PATIENT.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_document_type_model_creation() -> None:
    doc_type = DocumentType(
        id="01K4SRY37DGE7K5YWWKNB0TYPE",
        type="CPF",
    )

    assert doc_type.id == "01K4SRY37DGE7K5YWWKNB0TYPE"
    assert doc_type.type == "CPF"


def test_user_document_model_creation() -> None:
    user_doc = UserDocument(
        id="01K4SRY37DGE7K5YWWKNB0DOC1",
        user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        value="123.456.789-00",
        type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
    )

    assert user_doc.id == "01K4SRY37DGE7K5YWWKNB0DOC1"
    assert user_doc.user_id == "01K4SRY37DGE7K5YWWKNB0RESW"
    assert user_doc.value == "123.456.789-00"
    assert user_doc.type_id == "01K4SRY37DGE7K5YWWKNB0TYPE"


def test_user_document_relationship_one_to_one() -> None:
    user_doc = UserDocument(
        id="01K4SRY37DGE7K5YWWKNB0DOC1",
        user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        value="123.456.789-00",
        type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
    )
    user = User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="patient@example.com",
        full_name="Patient Example",
        document=user_doc,
        hashed_password="hashed-password",
        role=UserRole.PATIENT.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )

    assert user.document is user_doc
    assert user.document.user_id == user.id


def test_user_without_document_defaults_to_none() -> None:
    user = User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="patient@example.com",
        full_name="Patient Example",
        hashed_password="hashed-password",
        role=UserRole.PATIENT.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )

    assert user.document is None


def test_user_documents_table_schema_constraints() -> None:
    mapper = inspect(UserDocument)
    user_id_col = mapper.columns["user_id"]
    type_id_col = mapper.columns["type_id"]

    assert user_id_col.unique is True
    assert user_id_col.index is True
    assert type_id_col.index is True
    assert any(fk.target_fullname == "users.id" for fk in user_id_col.foreign_keys)
    assert any(
        fk.target_fullname == "document_type.id" for fk in type_id_col.foreign_keys
    )


def test_create_document_type_endpoint() -> None:
    app.dependency_overrides[get_auth_service] = FakeDocumentAuthService

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/document-types",
            json={"type": "CPF"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "id": "01K4SRY37DGE7K5YWWKNB0TYPE",
        "type": "CPF",
    }


def test_create_my_document_endpoint_returns_201() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_auth_service] = FakeDocumentAuthService

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/me/document",
            json={
                "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                "value": "123.456.789-00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "id": "01K4SRY37DGE7K5YWWKNB0DOC1",
        "user_id": "01K4SRY37DGE7K5YWWKNB0RESW",
        "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
        "value": "123.456.789-00",
    }


def test_create_my_document_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post(
        "/auth/me/document",
        json={
            "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
            "value": "123.456.789-00",
        },
    )

    assert response.status_code == 401


def test_create_my_document_endpoint_returns_404_when_type_not_found() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_auth_service] = lambda: FakeDocumentAuthService(
        missing_type=True
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/me/document",
            json={
                "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                "value": "123.456.789-00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Document type not found"}


def test_create_my_document_endpoint_returns_409_when_already_exists() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_auth_service] = lambda: FakeDocumentAuthService(
        already_exists=True
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/me/document",
            json={
                "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                "value": "123.456.789-00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "User already has a document"}


def test_register_endpoint_with_document_returns_201() -> None:
    app.dependency_overrides[get_auth_service] = FakeDocumentAuthService

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/register",
            json={
                "email": "patient@example.com",
                "full_name": "Patient Example",
                "password": "password123",
                "role": "patient",
                "document": {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "id": "01K4SRY37DGE7K5YWWKNB0RESW",
        "email": "patient@example.com",
        "full_name": "Patient Example",
        "role": "patient",
        "document": {
            "id": "01K4SRY37DGE7K5YWWKNB0DOC1",
            "user_id": "01K4SRY37DGE7K5YWWKNB0RESW",
            "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
            "value": "123.456.789-00",
        },
        "is_active": True,
        "created_at": "2026-09-09T00:00:00Z",
    }


def test_register_endpoint_with_invalid_document_type_returns_404() -> None:
    app.dependency_overrides[get_auth_service] = lambda: FakeDocumentAuthService(
        missing_type=True
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/auth/register",
            json={
                "email": "patient@example.com",
                "full_name": "Patient Example",
                "password": "password123",
                "document": {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                },
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Document type not found"}
