from pydantic import BaseModel, ConfigDict, Field


class DocumentTypeCreate(BaseModel):
    type: str = Field(min_length=1, max_length=255)


class DocumentTypeRead(BaseModel):
    id: str
    type: str

    model_config = ConfigDict(from_attributes=True)
