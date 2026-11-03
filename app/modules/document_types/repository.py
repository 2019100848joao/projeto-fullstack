from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.document_types.exceptions import DocumentTypeAlreadyExistsError
from app.modules.document_types.models import DocumentType


class DocumentTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, type_id: str) -> DocumentType | None:
        return self.db.get(DocumentType, type_id)

    def list_all(self) -> list[DocumentType]:
        statement = select(DocumentType).order_by(DocumentType.type, DocumentType.id)
        return list(self.db.scalars(statement).all())

    def create(self, *, doc_type: str) -> DocumentType:
        document_type = DocumentType(type=doc_type)
        self.db.add(document_type)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            statement = select(DocumentType).where(
                func.lower(func.trim(DocumentType.type)) == doc_type.strip().lower()
            )
            if self.db.scalar(statement) is not None:
                raise DocumentTypeAlreadyExistsError from exc
            raise
        self.db.refresh(document_type)
        return document_type
