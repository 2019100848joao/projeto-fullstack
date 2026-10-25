from app.core.security import create_access_token, hash_password, verify_password
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
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import (
    DocumentTypeCreate,
    Token,
    UserCreate,
    UserDocumentCreate,
)

ROLE_CHANGE_RULES: dict[UserRole, dict[UserRole, set[UserRole]]] = {
    UserRole.ADMIN: {
        UserRole.ADMIN: set(UserRole),
        UserRole.PATIENT: set(UserRole),
        UserRole.DOCTOR: set(UserRole),
        UserRole.ATTENDANT: set(UserRole),
    },
    UserRole.DOCTOR: {
        UserRole.ATTENDANT: {UserRole.PATIENT, UserRole.ATTENDANT},
    },
    UserRole.ATTENDANT: {
        UserRole.PATIENT: {UserRole.PATIENT, UserRole.ATTENDANT},
    },
}


class AuthService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def register(self, user_create: UserCreate) -> User:
        existing_user = self.repository.get_by_email(user_create.email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError

        document: UserDocument | None = None
        if user_create.document is not None:
            doc_type = self.repository.get_document_type_by_id(
                user_create.document.type_id
            )
            if doc_type is None:
                raise DocumentTypeNotFoundError

            document = UserDocument(
                type_id=user_create.document.type_id,
                value=user_create.document.value,
            )

        return self.repository.create(
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password=hash_password(user_create.password),
            role=UserRole(user_create.role),
            document=document,
        )

    def create_document_type(
        self,
        doc_type_create: DocumentTypeCreate,
    ) -> DocumentType:
        return self.repository.create_document_type(doc_type=doc_type_create.type)

    def create_user_document(
        self,
        *,
        current_user: User,
        doc_create: UserDocumentCreate,
    ) -> UserDocument:
        existing_doc = self.repository.get_document_by_user_id(current_user.id)
        if existing_doc is not None or current_user.document is not None:
            raise DocumentAlreadyExistsError

        doc_type = self.repository.get_document_type_by_id(doc_create.type_id)
        if doc_type is None:
            raise DocumentTypeNotFoundError

        return self.repository.create_user_document(
            user_id=current_user.id,
            type_id=doc_create.type_id,
            value=doc_create.value,
        )

    def login(self, *, email: str, password: str) -> Token:
        user = self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError

        if not user.is_active:
            raise InactiveUserError

        return Token(access_token=create_access_token(subject=user.id))

    def update_user_role(
        self,
        *,
        current_user: User,
        target_user_id: str,
        new_role: UserRole,
    ) -> User:
        target_user = self.repository.get_by_id(target_user_id)
        if target_user is None:
            raise UserNotFoundError

        current_role = UserRole(current_user.role)
        target_role = UserRole(target_user.role)
        allowed_target_roles = ROLE_CHANGE_RULES.get(current_role, {}).get(target_role)

        if allowed_target_roles is None or new_role not in allowed_target_roles:
            raise RoleChangeNotAllowedError

        return self.repository.update_role(target_user, new_role)
