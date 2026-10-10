from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.modules.appointments.enums import AgendaView, AppointmentStatus
from app.modules.appointments.exceptions import (
    AgendaDoctorRequiredError,
    AppointmentNotFoundError,
    AppointmentNotScheduledError,
    DoctorUnavailableError,
    InvalidDoctorError,
    InvalidPatientError,
)
from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import AppointmentRepository
from app.modules.appointments.schemas import (
    AgendaRead,
    AppointmentCreate,
)
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository


def agenda_period(view: AgendaView, day: date) -> tuple[datetime, datetime]:
    if view == AgendaView.DAY:
        first_day = day
        end_day = day + timedelta(days=1)
    elif view == AgendaView.WEEK:
        first_day = day - timedelta(days=day.weekday())
        end_day = first_day + timedelta(days=7)
    else:
        first_day = day.replace(day=1)
        end_day = (first_day + timedelta(days=32)).replace(day=1)

    timezone = ZoneInfo(settings.timezone)
    return (
        datetime.combine(first_day, time.min, timezone),
        datetime.combine(end_day, time.min, timezone),
    )


class AppointmentService:
    def __init__(
        self,
        repository: AppointmentRepository,
        user_repository: UserRepository,
    ) -> None:
        self.repository = repository
        self.user_repository = user_repository

    def schedule(
        self,
        *,
        current_user: User,
        appointment_create: AppointmentCreate,
    ) -> Appointment:
        patient = self.user_repository.get_by_id(appointment_create.patient_id)
        if patient is None or patient.role != UserRole.PATIENT.value:
            raise InvalidPatientError

        doctor = self.user_repository.get_by_id(appointment_create.doctor_id)
        if doctor is None or doctor.role != UserRole.DOCTOR.value:
            raise InvalidDoctorError

        if self.repository.doctor_has_conflict(
            doctor_id=doctor.id,
            scheduled_at=appointment_create.scheduled_at,
        ):
            raise DoctorUnavailableError

        return self.repository.create(
            patient_id=patient.id,
            doctor_id=doctor.id,
            created_by=current_user.id,
            scheduled_at=appointment_create.scheduled_at,
        )

    def list_appointments(
        self,
        *,
        doctor_id: str | None = None,
        patient_id: str | None = None,
    ) -> list[Appointment]:
        return self.repository.list(doctor_id=doctor_id, patient_id=patient_id)

    def reschedule(self, *, appointment_id: str, scheduled_at: datetime) -> Appointment:
        appointment = self._get_scheduled(appointment_id)

        if self.repository.doctor_has_conflict(
            doctor_id=appointment.doctor_id,
            scheduled_at=scheduled_at,
            ignore_appointment_id=appointment.id,
        ):
            raise DoctorUnavailableError

        return self.repository.reschedule(appointment, scheduled_at)

    def cancel(self, *, appointment_id: str) -> Appointment:
        return self.repository.cancel(self._get_scheduled(appointment_id))

    def get_agenda(
        self,
        *,
        current_user: User,
        view: AgendaView,
        day: date | None = None,
        doctor_id: str | None = None,
    ) -> AgendaRead:
        if current_user.role == UserRole.ADMIN.value:
            if doctor_id is None:
                raise AgendaDoctorRequiredError
        else:
            doctor_id = current_user.id

        if day is None:
            day = datetime.now(ZoneInfo(settings.timezone)).date()

        start, end = agenda_period(view, day)
        appointments = self.repository.list_for_doctor_between(
            doctor_id=doctor_id,
            start=start,
            end=end,
        )
        return AgendaRead.model_validate(
            {"view": view, "start": start, "end": end, "appointments": appointments},
            from_attributes=True,
        )

    def _get_scheduled(self, appointment_id: str) -> Appointment:
        appointment = self.repository.get_by_id(appointment_id)
        if appointment is None:
            raise AppointmentNotFoundError

        if appointment.status != AppointmentStatus.SCHEDULED.value:
            raise AppointmentNotScheduledError

        return appointment
