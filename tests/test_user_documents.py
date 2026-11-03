import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.core.database import Base
from app.main import app
from app.modules.auth.dependencies import get_auth_service, get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.schemas import UserCreate
from app.modules.document_types.dependencies import get_document_type_service
from app.modules.document_types.exceptions import DocumentTypeAlreadyExistsError
from app.modules.document_types.models import DocumentType
from app.modules.document_types.repository import DocumentTypeRepository
from app.modules.document_types.schemas import DocumentTypeCreate
from app.modules.document_types.service import DocumentTypeService
from app.modules.users.dependencies import get_user_service
from app.modules.users.exceptions import (
    DocumentAlreadyExistsError,
    DocumentTypeNotFoundError,
    DocumentValueAlreadyExistsError,
)
from app.modules.users.models import User, UserDocument
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserDocumentCreate, UserRead
from app.modules.users.service import UserService


class FakeDocumentTypeRepository:
    def list_all(self) -> list[DocumentType]:
        return [
            DocumentType(id="01K4SRY37DGE7K5YWWKNB0TYPE", type="CPF"),
            DocumentType(id="01K4SRY37DGE7K5YWWKNB0TYP2", type="CRM"),
        ]

    def create(self, *, doc_type: str) -> DocumentType:
        return DocumentType(
            id="01K4SRY37DGE7K5YWWKNB0TYPE",
            type=doc_type,
        )


class FakeDocumentTypeService:
    def list_all(self) -> list[DocumentType]:
        return FakeDocumentTypeRepository().list_all()

    def create(self, doc_type_create: DocumentTypeCreate) -> DocumentType:
        if doc_type_create.type == "DUPLICATE":
            raise DocumentTypeAlreadyExistsError
        return DocumentType(
            id="01K4SRY37DGE7K5YWWKNB0TYPE",
            type=doc_type_create.type,
        )


class FakeDocumentAuthService:
    def __init__(
        self,
        *,
        missing_type: bool = False,
        already_exists: bool = False,
        duplicate_value: bool = False,
    ) -> None:
        self.missing_type = missing_type
        self.already_exists = already_exists
        self.duplicate_value = duplicate_value

    def register(self, user_create: UserCreate) -> User:
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=user_create.email,
            full_name=user_create.full_name,
            documents=[],
            hashed_password="hashed-password",
            role=user_create.role.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def create_user_documents(
        self,
        *,
        current_user: User,
        doc_creates: list[UserDocumentCreate],
    ) -> list[UserDocument]:
        if self.missing_type:
            raise DocumentTypeNotFoundError
        if self.already_exists:
            raise DocumentAlreadyExistsError
        if self.duplicate_value:
            raise DocumentValueAlreadyExistsError
        return [
            UserDocument(
                id="01K4SRY37DGE7K5YWWKNB0DOC1",
                user_id=current_user.id,
                type_id=doc_create.type_id,
                value=doc_create.value,
                document_type=DocumentType(id=doc_create.type_id, type="CPF"),
            )
            for doc_create in doc_creates
        ]


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


def override_admin_user() -> User:
    user = override_current_user()
    user.role = UserRole.ADMIN.value
    return user


def test_document_type_model_creation() -> None:
    doc_type = DocumentType(
        id="01K4SRY37DGE7K5YWWKNB0TYPE",
        type="CPF",
    )

    assert doc_type.id == "01K4SRY37DGE7K5YWWKNB0TYPE"
    assert doc_type.type == "CPF"


def test_document_type_service_creates_document_type() -> None:
    service = DocumentTypeService(FakeDocumentTypeRepository())  # type: ignore[arg-type]

    doc_type = service.create(DocumentTypeCreate(type="CRM"))

    assert doc_type.id == "01K4SRY37DGE7K5YWWKNB0TYPE"
    assert doc_type.type == "CRM"


def test_document_type_service_lists_document_types() -> None:
    service = DocumentTypeService(FakeDocumentTypeRepository())  # type: ignore[arg-type]

    assert [doc_type.type for doc_type in service.list_all()] == ["CPF", "CRM"]


def test_document_type_repository_lists_all_in_stable_order() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all((DocumentType(type="CPF"), DocumentType(type="CRM")))
        db.commit()

        assert [item.type for item in DocumentTypeRepository(db).list_all()] == [
            "CPF",
            "CRM",
        ]


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


def test_user_document_relationship_one_to_many() -> None:
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
        documents=[user_doc],
        hashed_password="hashed-password",
        role=UserRole.PATIENT.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )

    assert user.document is user_doc
    assert user.documents == [user_doc]
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

    assert user_id_col.unique is not True
    assert any(
        constraint.name == "uq_user_documents_user_type"
        for constraint in UserDocument.__table__.constraints
    )
    assert user_id_col.index is True
    assert type_id_col.index is True
    assert any(fk.target_fullname == "users.id" for fk in user_id_col.foreign_keys)
    assert any(
        fk.target_fullname == "document_type.id" for fk in type_id_col.foreign_keys
    )


def test_create_document_type_endpoint() -> None:
    app.dependency_overrides[get_current_user] = override_admin_user
    app.dependency_overrides[get_document_type_service] = FakeDocumentTypeService

    try:
        client = TestClient(app)
        response = client.post(
            "/document-types",
            json={"type": "CPF"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == {
        "id": "01K4SRY37DGE7K5YWWKNB0TYPE",
        "type": "CPF",
    }


def test_user_document_route_is_separate_from_auth_routes() -> None:
    paths = app.openapi()["paths"]
    auth_paths = {path for path in paths if path.startswith("/auth/")}
    assert auth_paths == {
        "/auth/register",
        "/auth/login",
        "/auth/me",
        "/auth/{user_id}/role",
    }
    assert paths["/users/me/documents"]["post"]["tags"] == ["users"]


def test_list_document_types_is_public() -> None:
    app.dependency_overrides[get_document_type_service] = FakeDocumentTypeService

    try:
        response = TestClient(app).get("/document-types")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == [
        {"id": "01K4SRY37DGE7K5YWWKNB0TYPE", "type": "CPF"},
        {"id": "01K4SRY37DGE7K5YWWKNB0TYP2", "type": "CRM"},
    ]


def test_create_document_type_requires_authentication() -> None:
    app.dependency_overrides[get_document_type_service] = FakeDocumentTypeService

    try:
        response = TestClient(app).post("/document-types", json={"type": "CPF"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


def test_create_document_type_requires_admin_role() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_document_type_service] = FakeDocumentTypeService

    try:
        response = TestClient(app).post("/document-types", json={"type": "CPF"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_create_document_type_returns_409_when_duplicate() -> None:
    app.dependency_overrides[get_current_user] = override_admin_user
    app.dependency_overrides[get_document_type_service] = FakeDocumentTypeService

    try:
        response = TestClient(app).post(
            "/document-types", json={"type": "DUPLICATE"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_create_document_type_rejects_blank_type() -> None:
    app.dependency_overrides[get_current_user] = override_admin_user

    try:
        response = TestClient(app).post("/document-types", json={"type": "   "})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422

def test_document_type_repository_rejects_normalized_duplicate() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE UNIQUE INDEX ux_document_type_normalized_type "
                "ON document_type (lower(trim(type)))"
            )
        )

    with Session(engine) as db:
        repository = DocumentTypeRepository(db)
        repository.create(doc_type="CPF")

        with pytest.raises(DocumentTypeAlreadyExistsError):
            repository.create(doc_type=" cpf ")


def test_create_my_documents_endpoint_returns_list_for_one_document() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = FakeDocumentAuthService

    try:
        client = TestClient(app)
        response = client.post(
            "/users/me/documents",
            json=[
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                }
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json() == [
        {
            "id": "01K4SRY37DGE7K5YWWKNB0DOC1",
            "user_id": "01K4SRY37DGE7K5YWWKNB0RESW",
            "value": "123.456.789-00",
            "document_type": {
                "id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                "type": "CPF",
            },
        }
    ]


def test_create_my_documents_endpoint_rejects_object_body() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = FakeDocumentAuthService

    try:
        response = TestClient(app).post(
            "/users/me/documents",
            json={
                "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                "value": "123.456.789-00",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_create_my_documents_endpoint_accepts_batch() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = FakeDocumentAuthService

    try:
        response = TestClient(app).post(
            "/users/me/documents",
            json=[
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                },
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYP2",
                    "value": "CRM-123456",
                },
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert len(response.json()) == 2
    assert [item["value"] for item in response.json()] == [
        "123.456.789-00",
        "CRM-123456",
    ]


def test_create_my_documents_endpoint_rejects_empty_batch() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = FakeDocumentAuthService

    try:
        response = TestClient(app).post("/users/me/documents", json=[])
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_create_my_document_requires_authentication() -> None:
    client = TestClient(app)

    response = client.post(
        "/users/me/documents",
        json=[
            {
                "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                "value": "123.456.789-00",
            }
        ],
    )

    assert response.status_code == 401


def test_create_my_document_endpoint_returns_404_when_type_not_found() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = lambda: FakeDocumentAuthService(
        missing_type=True
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/users/me/documents",
            json=[
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                }
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Document type not found"}


def test_create_my_document_endpoint_returns_409_when_already_exists() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = lambda: FakeDocumentAuthService(
        already_exists=True
    )

    try:
        client = TestClient(app)
        response = client.post(
            "/users/me/documents",
            json=[
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                }
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "User already has a document of this type"}


def test_create_my_document_returns_409_when_value_is_registered() -> None:
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_user_service] = lambda: FakeDocumentAuthService(
        duplicate_value=True
    )

    try:
        response = TestClient(app).post(
            "/users/me/documents",
            json=[
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "123.456.789-00",
                }
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {"detail": "Document value is already registered"}


def test_create_my_document_rejects_punctuation_only_value() -> None:
    app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = TestClient(app).post(
            "/users/me/documents",
            json=[
                {
                    "type_id": "01K4SRY37DGE7K5YWWKNB0TYPE",
                    "value": "---",
                }
            ],
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_repository_maps_duplicate_user_document_to_domain_error() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            email="patient@example.com",
            full_name="Patient Example",
            hashed_password="hashed-password",
        )
        doc_type = DocumentType(type="CPF")
        db.add_all((user, doc_type))
        db.commit()

        repository = UserRepository(db)
        repository.create_user_documents(
            user_id=user.id,
            documents=[(doc_type.id, "123.456.789-00")],
        )

        with pytest.raises(DocumentAlreadyExistsError):
            repository.create_user_documents(
                user_id=user.id,
                documents=[(doc_type.id, "999.999.999-99")],
            )


def test_service_creates_distinct_document_types_in_one_batch() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        cpf = DocumentType(type="CPF")
        crm = DocumentType(type="CRM")
        db.add_all((cpf, crm))
        db.commit()

        repository = UserRepository(db)
        user = repository.create(
            email="patient@example.com",
            full_name="Patient Example",
            hashed_password="hashed-password",
        )
        created = UserService(repository).create_user_documents(
            current_user=user,
            doc_creates=[
                UserDocumentCreate(type_id=cpf.id, value="123.456.789-00"),
                UserDocumentCreate(type_id=crm.id, value="CRM-123456"),
            ],
        )

        assert len(created) == 2
        assert {document.type_id for document in user.documents} == {cpf.id, crm.id}
        read_user = UserRead.model_validate(user)
        assert {document.document_type.type for document in read_user.documents} == {
            "CPF",
            "CRM",
        }


def test_batch_rejects_duplicate_type_without_writing() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        doc_type = DocumentType(type="CPF")
        db.add(doc_type)
        db.commit()
        repository = UserRepository(db)
        user = repository.create(
            email="patient@example.com",
            full_name="Patient Example",
            hashed_password="hashed-password",
        )

        with pytest.raises(DocumentAlreadyExistsError):
            UserService(repository).create_user_documents(
                current_user=user,
                doc_creates=[
                    UserDocumentCreate(type_id=doc_type.id, value="12345678900"),
                    UserDocumentCreate(type_id=doc_type.id, value="99999999999"),
                ],
            )

        assert db.scalars(select(UserDocument)).all() == []


def test_batch_rolls_back_when_one_insert_conflicts() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        cpf = DocumentType(type="CPF")
        crm = DocumentType(type="CRM")
        db.add_all((cpf, crm))
        db.commit()
        repository = UserRepository(db)
        user = repository.create(
            email="patient@example.com",
            full_name="Patient Example",
            hashed_password="hashed-password",
        )
        repository.create_user_documents(
            user_id=user.id, documents=[(cpf.id, "12345678900")]
        )

        with pytest.raises(DocumentAlreadyExistsError):
            repository.create_user_documents(
                user_id=user.id,
                documents=[
                    (crm.id, "CRM-123456"),
                    (cpf.id, "99999999999"),
                ],
            )

        assert repository.get_document_by_user_and_type(user.id, crm.id) is None


def test_register_endpoint_without_document_returns_201() -> None:
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
        "documents": [],
        "is_active": True,
        "created_at": "2026-09-09T00:00:00Z",
    }


def test_register_rejects_document_payload() -> None:
    app.dependency_overrides[get_auth_service] = FakeDocumentAuthService

    try:
        response = TestClient(app).post(
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

    assert response.status_code == 422
