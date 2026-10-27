from fastapi import APIRouter, status

from app.modules.document_types.dependencies import DocumentTypeServiceDep
from app.modules.document_types.models import DocumentType
from app.modules.document_types.schemas import DocumentTypeCreate, DocumentTypeRead

router = APIRouter(prefix="/document-types", tags=["document-types"])


@router.post("", response_model=DocumentTypeRead, status_code=status.HTTP_201_CREATED)
def create_document_type(
    doc_type_create: DocumentTypeCreate,
    service: DocumentTypeServiceDep,
) -> DocumentType:
    return service.create(doc_type_create)
