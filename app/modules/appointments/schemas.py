from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.appointments.enums import AppointmentStatus


class AppointmentCreate(BaseModel):
    doctor_id: str = Field(min_length=26, max_length=26)
    patient_id: str = Field(min_length=26, max_length=26)
    starts_at: datetime
    ends_at: datetime
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("Datetime must include timezone information")

        return value


class AppointmentRead(BaseModel):
    id: str
    doctor_id: str
    patient_id: str
    created_by_id: str
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    reason: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
