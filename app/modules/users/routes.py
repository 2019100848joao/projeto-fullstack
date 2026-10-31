from fastapi import APIRouter, HTTPException, status

from app.modules.auth.dependencies import CurrentUserDep
from app.modules.users.dependencies import UserServiceDep
from app.modules.users.exceptions import (
    DocumentAlreadyExistsError,
    DocumentTypeNotFoundError,
    DocumentValueAlreadyExistsError,
)
from app.modules.users.models import UserDocument
from app.modules.users.schemas import (
    UserDocumentCreate,
    UserDocumentRead,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post(
    "/me/documents",
    response_model=UserDocumentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_current_user_document(
    doc_create: UserDocumentCreate,
    current_user: CurrentUserDep,
    user_service: UserServiceDep,
) -> UserDocument:
    try:
        return user_service.create_user_document(
            current_user=current_user,
            doc_create=doc_create,
        )
    except DocumentTypeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document type not found",
        ) from exc
    except DocumentAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already has a document of this type",
        ) from exc
    except DocumentValueAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document value is already registered",
        ) from exc
