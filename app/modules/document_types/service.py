from app.modules.document_types.models import DocumentType
from app.modules.document_types.repository import DocumentTypeRepository
from app.modules.document_types.schemas import DocumentTypeCreate


class DocumentTypeService:
    def __init__(self, repository: DocumentTypeRepository) -> None:
        self.repository = repository

    def create(self, doc_type_create: DocumentTypeCreate) -> DocumentType:
        return self.repository.create(doc_type=doc_type_create.type)

    def list_all(self) -> list[DocumentType]:
        return self.repository.list_all()
