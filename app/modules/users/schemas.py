from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.enums import UserRole
from app.modules.document_types.schemas import DocumentTypeRead


class UserDocumentCreate(BaseModel):
    type_id: str = Field(min_length=26, max_length=26)
    value: str = Field(min_length=1, max_length=255)

    @field_validator("value")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("Document value must contain a letter or digit")
        return value


UserDocumentBatchCreate = Annotated[list[UserDocumentCreate], Field(min_length=1)]


class UserDocumentRead(BaseModel):
    id: str
    user_id: str
    value: str
    document_type: DocumentTypeRead

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    documents: list[UserDocumentRead] = Field(default_factory=list)
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
