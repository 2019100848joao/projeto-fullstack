from app.modules.users.exceptions import (
    DocumentAlreadyExistsError,
    DocumentTypeNotFoundError,
)
from app.modules.users.models import User, UserDocument
from app.modules.users.repository import UserRepository
from app.modules.users.schemas import UserDocumentCreate


class UserService:
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    def create_user_document(
        self,
        *,
        current_user: User,
        doc_create: UserDocumentCreate,
    ) -> UserDocument:
        existing_doc = self.repository.get_document_by_user_and_type(
            current_user.id, doc_create.type_id
        )
        if existing_doc is not None:
            raise DocumentAlreadyExistsError

        doc_type = self.repository.get_document_type_by_id(doc_create.type_id)
        if doc_type is None:
            raise DocumentTypeNotFoundError

        return self.repository.create_user_document(
            user_id=current_user.id,
            type_id=doc_create.type_id,
            value=doc_create.value,
        )
