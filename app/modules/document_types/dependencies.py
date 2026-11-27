from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.document_types.repository import DocumentTypeRepository
from app.modules.document_types.service import DocumentTypeService

DbSession = Annotated[Session, Depends(get_db)]


def get_document_type_service(db: DbSession) -> DocumentTypeService:
    return DocumentTypeService(DocumentTypeRepository(db))


DocumentTypeServiceDep = Annotated[
    DocumentTypeService,
    Depends(get_document_type_service),
]
