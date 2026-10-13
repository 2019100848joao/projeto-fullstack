from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.modules.appointments.schemas import UserSummary
from app.modules.exams.enums import ExamStatus


class ExamSchedule(BaseModel):
    scheduled_at: AwareDatetime


class ExamResultCreate(BaseModel):
    result: str = Field(min_length=1, max_length=20000)


class ExamRead(BaseModel):
    id: str
    appointment_id: str
    name: str
    status: ExamStatus
    patient: UserSummary
    doctor: UserSummary
    scheduled_at: datetime | None
    performed_at: datetime | None
    result: str | None
    result_available_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
