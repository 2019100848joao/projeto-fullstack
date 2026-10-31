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

    def create_user_documents(
        self,
        *,
        current_user: User,
        doc_creates: list[UserDocumentCreate],
    ) -> list[UserDocument]:
        if not doc_creates:
            raise ValueError("At least one document is required")

        seen_types: set[str] = set()
        for doc_create in doc_creates:
            if doc_create.type_id in seen_types:
                raise DocumentAlreadyExistsError
            seen_types.add(doc_create.type_id)

            existing_doc = self.repository.get_document_by_user_and_type(
                current_user.id, doc_create.type_id
            )
            if existing_doc is not None:
                raise DocumentAlreadyExistsError

            if self.repository.get_document_type_by_id(doc_create.type_id) is None:
                raise DocumentTypeNotFoundError

        return self.repository.create_user_documents(
            user_id=current_user.id,
            documents=[
                (doc_create.type_id, doc_create.value) for doc_create in doc_creates
            ],
        )
