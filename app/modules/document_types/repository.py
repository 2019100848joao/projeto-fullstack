from sqlalchemy.orm import Session

from app.modules.document_types.models import DocumentType


class DocumentTypeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, type_id: str) -> DocumentType | None:
        return self.db.get(DocumentType, type_id)

    def create(self, *, doc_type: str) -> DocumentType:
        document_type = DocumentType(type=doc_type)
        self.db.add(document_type)
        self.db.commit()
        self.db.refresh(document_type)
        return document_type
