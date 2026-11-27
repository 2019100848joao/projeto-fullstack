from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import AdminUserDep
from app.modules.document_types.dependencies import DocumentTypeServiceDep
from app.modules.document_types.exceptions import DocumentTypeAlreadyExistsError
from app.modules.document_types.models import DocumentType
from app.modules.document_types.schemas import DocumentTypeCreate, DocumentTypeRead

router = APIRouter(prefix="/document-types", tags=["document-types"])


@router.get("", response_model=list[DocumentTypeRead])
def list_document_types(service: DocumentTypeServiceDep) -> list[DocumentType]:
    return service.list_all()


@router.post("", response_model=DocumentTypeRead, status_code=status.HTTP_201_CREATED)
def create_document_type(
    doc_type_create: DocumentTypeCreate,
    _: AdminUserDep,
    service: DocumentTypeServiceDep,
) -> DocumentType:
    try:
        return service.create(doc_type_create)
    except DocumentTypeAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document type already exists",
        ) from exc
