from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.enums import UserRole
from app.modules.auth.models import DocumentType, User, UserDocument


class UserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> User | None:
        statement = select(User).where(User.email == email)
        return self.db.scalar(statement)

    def update_role(self, user: User, role: UserRole) -> User:
        user.role = role.value
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
            document=document,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_document_type_by_id(self, type_id: str) -> DocumentType | None:
        return self.db.get(DocumentType, type_id)

    def create_document_type(self, *, doc_type: str) -> DocumentType:
        document_type = DocumentType(type=doc_type)
        self.db.add(document_type)
        self.db.commit()
        self.db.refresh(document_type)
        return document_type

    def get_document_by_user_id(self, user_id: str) -> UserDocument | None:
        statement = select(UserDocument).where(UserDocument.user_id == user_id)
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
        self.db.commit()
        self.db.refresh(document)
        return document
