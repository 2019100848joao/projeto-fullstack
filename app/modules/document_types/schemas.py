from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentTypeCreate(BaseModel):
    type: str = Field(min_length=1, max_length=255)

    @field_validator("type")
    @classmethod
    def reject_blank_type(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Document type cannot be blank")
        return value


class DocumentTypeRead(BaseModel):
    id: str
    type: str

    model_config = ConfigDict(from_attributes=True)
