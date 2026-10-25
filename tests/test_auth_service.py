from datetime import UTC, datetime

import pytest

from app.core.security import hash_password
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    DocumentAlreadyExistsError,
    DocumentTypeNotFoundError,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.models import DocumentType, User, UserDocument
from app.modules.auth.schemas import (
    DocumentTypeCreate,
    RegistrationRole,
    UserCreate,
    UserDocumentCreate,
)
from app.modules.auth.service import AuthService


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

    def update_role(self, user: User, role: UserRole) -> User:
        user.role = role.value
        return user

    def create(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.PATIENT,
        document: UserDocument | None = None,
    ) -> User:
        self.created_role = role
        if document is not None:
            document.id = "01K4SRY37DGE7K5YWWKNB0DOC1"
            document.user_id = "01K4SRY37DGE7K5YWWKNB0RESW"
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=email,
            full_name=full_name,
            document=document,
            hashed_password=hashed_password,
            role=role.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def get_document_type_by_id(self, type_id: str) -> DocumentType | None:
        if self.doc_type is not None and self.doc_type.id == type_id:
            return self.doc_type
        return None

    def create_document_type(self, *, doc_type: str) -> DocumentType:
        created = DocumentType(
            id="01K4SRY37DGE7K5YWWKNB0TYPE",
            type=doc_type,
        )
        self.doc_type = created
        return created

    def get_document_by_user_id(self, user_id: str) -> UserDocument | None:
        return self.user_document

    def create_user_document(
        self,
        *,
        user_id: str,
        type_id: str,
        value: str,
    ) -> UserDocument:
        created = UserDocument(
            id="01K4SRY37DGE7K5YWWKNB0DOC1",
            user_id=user_id,
            type_id=type_id,
            value=value,
        )
        self.user_document = created
        return created


def test_register_raises_domain_error_when_email_exists() -> None:
    service = AuthService(
        FakeUserRepository(
            User(
                id="01K4SRY37DGE7K5YWWKNB0RESW",
                email="doctor@example.com",
                full_name="Dr. Example",
                document=None,
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


def test_register_with_document_creates_user_and_document() -> None:
    doc_type = DocumentType(id="01K4SRY37DGE7K5YWWKNB0TYPE", type="CPF")
    repository = FakeUserRepository(doc_type=doc_type)
    service = AuthService(repository)

    user = service.register(
        UserCreate(
            email="patient@example.com",
            full_name="Patient Example",
            password="password123",
            document=UserDocumentCreate(
                type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                value="123.456.789-00",
            ),
        )
    )

    assert user.document is not None
    assert user.document.type_id == "01K4SRY37DGE7K5YWWKNB0TYPE"
    assert user.document.value == "123.456.789-00"


def test_register_with_unknown_document_type_raises_error() -> None:
    service = AuthService(FakeUserRepository())

    with pytest.raises(DocumentTypeNotFoundError):
        service.register(
            UserCreate(
                email="patient@example.com",
                full_name="Patient Example",
                password="password123",
                document=UserDocumentCreate(
                    type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                    value="123.456.789-00",
                ),
            )
        )


def test_create_document_type_saves_new_type() -> None:
    service = AuthService(FakeUserRepository())

    doc_type = service.create_document_type(DocumentTypeCreate(type="CRM"))

    assert doc_type.id == "01K4SRY37DGE7K5YWWKNB0TYPE"
    assert doc_type.type == "CRM"


def test_create_user_document_links_to_current_user() -> None:
    doc_type = DocumentType(id="01K4SRY37DGE7K5YWWKNB0TYPE", type="CPF")
    service = AuthService(FakeUserRepository(doc_type=doc_type))
    current_user = make_user(UserRole.PATIENT)

    doc = service.create_user_document(
        current_user=current_user,
        doc_create=UserDocumentCreate(
            type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
            value="123.456.789-00",
        ),
    )

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
    service = AuthService(FakeUserRepository(user_document=existing_doc))

    with pytest.raises(DocumentAlreadyExistsError):
        service.create_user_document(
            current_user=make_user(UserRole.PATIENT, document=existing_doc),
            doc_create=UserDocumentCreate(
                type_id="01K4SRY37DGE7K5YWWKNB0TYPE",
                value="999.999.999-99",
            ),
        )


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
                document=None,
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
        document=document,
        hashed_password=hash_password("password123"),
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )
