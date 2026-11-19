from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
)

from app.modules.appointments.enums import AppointmentStatus, CalendarView
from app.modules.exams.enums import ExamStatus

# Appointments use a fixed grid, so two appointments of the same doctor
# overlap only when they start at the same time. That lets the unique index
# ux_appointments_doctor_active_slot reject every overlap.
SLOT_MINUTES = 30


def _in_the_future(value: datetime) -> datetime:
    if value <= datetime.now(UTC):
        raise ValueError("must be in the future")
    return value


def _on_slot_grid(value: datetime) -> datetime:
    # Checked in UTC so offsets such as +05:45 cannot shift a slot off the grid.
    utc_value = value.astimezone(UTC)
    if utc_value.minute % SLOT_MINUTES or utc_value.second or utc_value.microsecond:
        raise ValueError(f"must start on a {SLOT_MINUTES}-minute slot")
    return value


FutureDatetime = Annotated[AwareDatetime, AfterValidator(_in_the_future)]
AppointmentSlot = Annotated[FutureDatetime, AfterValidator(_on_slot_grid)]

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
    scheduled_at: AppointmentSlot


class AppointmentReschedule(BaseModel):
    scheduled_at: AppointmentSlot


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


class CalendarRead(BaseModel):
    view: CalendarView
    start: datetime
    end: datetime
    appointments: list[AppointmentDetailRead]
