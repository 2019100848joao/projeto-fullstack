from datetime import UTC, datetime

import pytest

from app.core.security import hash_password
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.schemas import RegistrationRole, UserCreate
from app.modules.auth.service import AuthService
from app.modules.document_types.models import DocumentType
from app.modules.users.exceptions import (
    DocumentAlreadyExistsError,
    DocumentTypeNotFoundError,
)
from app.modules.users.models import User, UserDocument
from app.modules.users.schemas import UserDocumentCreate
from app.modules.users.service import UserService


class FakeUserRepository:
    def __init__(
        self,
        user: User | None = None,
        doc_type: DocumentType | None = None,
        user_document: UserDocument | None = None,
    ) -> None:
        self.user = user
        self.doc_type = doc_type
        self.user_document = user_document
        self.created_role: UserRole | None = None

    def get_by_email(self, email: str) -> User | None:
        return self.user

    def get_by_id(self, user_id: str) -> User | None:
        return self.user

    def save(self, user: User) -> User:
        return user

    def create(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.PATIENT,
    ) -> User:
        self.created_role = role
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=email,
            full_name=full_name,
            documents=[],
            hashed_password=hashed_password,
            role=role.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def get_document_type_by_id(self, type_id: str) -> DocumentType | None:
        if self.doc_type is not None and self.doc_type.id == type_id:
            return self.doc_type
        return None

    def get_document_by_user_and_type(
        self, user_id: str, type_id: str
    ) -> UserDocument | None:
        if self.user_document is not None and self.user_document.type_id == type_id:
            return self.user_document
        return None

    def create_user_documents(
        self,
        *,
        user_id: str,
        documents: list[tuple[str, str]],
    ) -> list[UserDocument]:
        created = [
            UserDocument(
                id="01K4SRY37DGE7K5YWWKNB0DOC1",
                user_id=user_id,
                type_id=type_id,
                value=value,
            )
            for type_id, value in documents
        ]
        if created:
            self.user_document = created[-1]
        return created


def test_register_raises_domain_error_when_email_exists() -> None:
    service = AuthService(
        FakeUserRepository(
            User(
                id="01K4SRY37DGE7K5YWWKNB0RESW",
                email="doctor@example.com",
                full_name="Dr. Example",
                documents=[],
                hashed_password="hashed",
                role="doctor",
                is_active=True,
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register(
            UserCreate(
                email="doctor@example.com",
                full_name="Dr. Example",
                password="password123",
            )
        )


def test_register_accepts_non_admin_role() -> None:
    repository = FakeUserRepository()
    service = AuthService(repository)

    user = service.register(
        UserCreate(
            email="doctor@example.com",
            full_name="Dr. Example",
            password="password123",
            role=RegistrationRole.DOCTOR,
        )
    )

    assert repository.created_role == UserRole.DOCTOR
    assert user.role == "doctor"
    assert user.document is None


def test_create_user_document_with_unknown_type_raises_error() -> None:
    service = UserService(FakeUserRepository())

    with pytest.raises(DocumentTypeNotFoundError):
        service.create_user_documents(
            current_user=make_user(UserRole.PATIENT),
            doc_creates=[
                UserDocumentCreate(
                    type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                    value="123.456.789-00",
                )
            ],
        )


def test_create_user_document_links_to_current_user() -> None:
    doc_type = DocumentType(id="01K4SRY37DGE7K5YWWKNB0TYPE", type="CPF")
    service = UserService(FakeUserRepository(doc_type=doc_type))
    current_user = make_user(UserRole.PATIENT)

    docs = service.create_user_documents(
        current_user=current_user,
        doc_creates=[
            UserDocumentCreate(
                type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                value="123.456.789-00",
            )
        ],
    )

    assert len(docs) == 1
    doc = docs[0]
    assert doc.user_id == current_user.id
    assert doc.type_id == "01K4SRY37DGE7K5YWWKNB0TYPE"
    assert doc.value == "123.456.789-00"


def test_create_user_document_raises_when_already_exists() -> None:
    existing_doc = UserDocument(
        id="01K4SRY37DGE7K5YWWKNB0DOC1",
        user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
        value="123.456.789-00",
    )
    service = UserService(FakeUserRepository(user_document=existing_doc))

    with pytest.raises(DocumentAlreadyExistsError):
        service.create_user_documents(
            current_user=make_user(UserRole.PATIENT, document=existing_doc),
            doc_creates=[
                UserDocumentCreate(
                    type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                    value="999.999.999-99",
                )
            ],
        )


def test_create_user_document_allows_another_type() -> None:
    existing_doc = UserDocument(
        id="01K4SRY37DGE7K5YWWKNB0DOC1",
        user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
        value="123.456.789-00",
    )
    new_type = DocumentType(id="01K4SRY37DGE7K5YWWKNB0TYP2", type="CRM")
    service = UserService(
        FakeUserRepository(doc_type=new_type, user_document=existing_doc)
    )

    created = service.create_user_documents(
        current_user=make_user(UserRole.PATIENT, document=existing_doc),
        doc_creates=[
            UserDocumentCreate(
                type_id=new_type.id,
                value="CRM-123456",
            )
        ],
    )

    assert created[0].type_id == new_type.id


def test_login_raises_domain_error_when_credentials_are_invalid() -> None:
    service = AuthService(FakeUserRepository())

    with pytest.raises(InvalidCredentialsError):
        service.login(email="doctor@example.com", password="wrong-password")


def test_login_raises_domain_error_when_user_is_inactive() -> None:
    service = AuthService(
        FakeUserRepository(
            User(
                id="01K4SRY37DGE7K5YWWKNB0RESW",
                email="doctor@example.com",
                full_name="Dr. Example",
                documents=[],
                hashed_password=hash_password("password123"),
                role="doctor",
                is_active=False,
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )
    )

    with pytest.raises(InactiveUserError):
        service.login(email="doctor@example.com", password="password123")


def test_admin_can_change_any_user_role() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.PATIENT)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.ADMIN),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=UserRole.DOCTOR,
    )

    assert updated_user.role == "doctor"


def test_doctor_can_change_attendant_to_patient() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.ATTENDANT)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.DOCTOR),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=UserRole.PATIENT,
    )

    assert updated_user.role == "patient"


def test_attendant_can_change_patient_to_attendant() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.PATIENT)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.ATTENDANT),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=UserRole.ATTENDANT,
    )

    assert updated_user.role == "attendant"


def test_role_change_rejects_disallowed_change() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.PATIENT)))

    with pytest.raises(RoleChangeNotAllowedError):
        service.update_user_role(
            current_user=make_user(UserRole.DOCTOR),
            target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
            new_role=UserRole.ADMIN,
        )


def test_role_change_raises_when_user_does_not_exist() -> None:
    service = AuthService(FakeUserRepository())

    with pytest.raises(UserNotFoundError):
        service.update_user_role(
            current_user=make_user(UserRole.ADMIN),
            target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
            new_role=UserRole.DOCTOR,
        )


def test_user_can_hold_single_document() -> None:
    doc_type = DocumentType(
        id="01K4SRY37DGE7K5YWWKNB0TYPE",
        type="CPF",
    )
    user_doc = UserDocument(
        id="01K4SRY37DGE7K5YWWKNB0DOC1",
        user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        value="123.456.789-00",
        type_id=doc_type.id,
    )
    user = make_user(UserRole.PATIENT, document=user_doc)

    assert user.document is not None
    assert user.document.id == "01K4SRY37DGE7K5YWWKNB0DOC1"
    assert user.document.value == "123.456.789-00"
    assert user.document.type_id == doc_type.id


def make_user(
    role: UserRole,
    document: UserDocument | None = None,
) -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="doctor@example.com",
        full_name="Dr. Example",
        documents=[document] if document is not None else [],
        hashed_password=hash_password("password123"),
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )
