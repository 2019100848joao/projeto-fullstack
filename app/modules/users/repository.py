from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.auth.enums import UserRole
from app.modules.document_types.models import DocumentType
from app.modules.users.exceptions import (
    DocumentAlreadyExistsError,
    DocumentValueAlreadyExistsError,
)
from app.modules.users.models import User, UserDocument


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def save(self, user: User) -> User:
        self.db.commit()
        self.db.refresh(user)
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
        user = User(
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role.value,
            documents=[document] if document is not None else [],
        )
        self.db.add(user)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if _is_duplicate_document_value(exc):
                raise DocumentValueAlreadyExistsError from exc
            raise
        self.db.refresh(user)
        return user

    def get_document_type_by_id(self, type_id: str) -> DocumentType | None:
        return self.db.get(DocumentType, type_id)

    def get_document_by_user_and_type(
        self, user_id: str, type_id: str
    ) -> UserDocument | None:
        statement = select(UserDocument).where(
            UserDocument.user_id == user_id,
            UserDocument.type_id == type_id,
        )
        return self.db.scalar(statement)

    def create_user_document(
        self,
        *,
        user_id: str,
        type_id: str,
        value: str,
    ) -> UserDocument:
        document = UserDocument(
            user_id=user_id,
            type_id=type_id,
            value=value,
        )
        self.db.add(document)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            if self.get_document_by_user_and_type(user_id, type_id) is not None:
                raise DocumentAlreadyExistsError from exc
            if _is_duplicate_document_value(exc):
                raise DocumentValueAlreadyExistsError from exc
            raise
        self.db.refresh(document)
        return document


def _is_duplicate_document_value(exc: IntegrityError) -> bool:
    diagnostic = getattr(exc.orig, "diag", None)
    return (
        getattr(diagnostic, "constraint_name", None)
        == "ux_user_documents_type_value"
    )
