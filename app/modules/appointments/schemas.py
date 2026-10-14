from datetime import datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.modules.appointments.enums import AgendaView, AppointmentStatus
from app.modules.exams.enums import ExamStatus

ExamName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=255),
]


class UserSummary(BaseModel):
    id: str
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ExamSummary(BaseModel):
    id: str
    name: str
    status: ExamStatus

    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    scheduled_at: AwareDatetime


class AppointmentReschedule(BaseModel):
    scheduled_at: AwareDatetime


class AttendanceCreate(BaseModel):
    observations: str | None = Field(default=None, max_length=5000)
    consultation_info: str | None = Field(default=None, max_length=5000)
    exam_requests: list[ExamName] = Field(default_factory=list, max_length=50)


class AppointmentRead(BaseModel):
    id: str
    patient: UserSummary
    doctor: UserSummary
    scheduled_at: datetime
    status: AppointmentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AppointmentDetailRead(AppointmentRead):
    observations: str | None
    consultation_info: str | None
    attended_at: datetime | None
    exams: list[ExamSummary]


class AgendaRead(BaseModel):
    view: AgendaView
    start: datetime
    end: datetime
    appointments: list[AppointmentDetailRead]
