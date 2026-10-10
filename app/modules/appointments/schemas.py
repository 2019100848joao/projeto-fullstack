from datetime import datetime

from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.modules.appointments.enums import AgendaView, AppointmentStatus


class UserSummary(BaseModel):
    id: str
    full_name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class AppointmentCreate(BaseModel):
    patient_id: str
    doctor_id: str
    scheduled_at: AwareDatetime


class AppointmentReschedule(BaseModel):
    scheduled_at: AwareDatetime


class AppointmentRead(BaseModel):
    id: str
    patient: UserSummary
    doctor: UserSummary
    scheduled_at: datetime
    status: AppointmentStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgendaRead(BaseModel):
    view: AgendaView
    start: datetime
    end: datetime
    appointments: list[AppointmentRead]
