from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.enums import UserRole
from app.modules.users.schemas import UserDocumentCreate


class RegistrationRole(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ATTENDANT = "attendant"


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    role: RegistrationRole = RegistrationRole.PATIENT
    document: UserDocumentCreate | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRoleUpdate(BaseModel):
    role: UserRole
