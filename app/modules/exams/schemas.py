from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, StringConstraints

from app.modules.appointments.schemas import UserSummary
from app.modules.exams.enums import ExamStatus

ExamResultText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=20000),
]


class ExamSchedule(BaseModel):
    scheduled_at: AwareDatetime


class ExamResultCreate(BaseModel):
    result: ExamResultText


class ExamRead(BaseModel):
    id: str
    appointment_id: str
    name: str
    status: ExamStatus
    patient: UserSummary
    doctor: UserSummary
    scheduled_at: datetime | None
    performed_at: datetime | None
    result_available_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExamResultRead(ExamRead):
    result: str
