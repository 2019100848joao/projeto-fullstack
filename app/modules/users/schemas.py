from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.enums import UserRole


class UserDocumentCreate(BaseModel):
    type_id: str = Field(min_length=26, max_length=26)
    value: str = Field(min_length=1, max_length=255)

    @field_validator("value")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not any(character.isalnum() for character in value):
            raise ValueError("Document value must contain a letter or digit")
        return value


class UserDocumentRead(BaseModel):
    id: str
    user_id: str
    type_id: str
    value: str

    model_config = ConfigDict(from_attributes=True)


class UserRead(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    role: UserRole
    document: UserDocumentRead | None = None
    documents: list[UserDocumentRead] = Field(default_factory=list)
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
