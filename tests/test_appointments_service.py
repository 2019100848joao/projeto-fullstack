from datetime import UTC, date, datetime

import pytest

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
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import AppointmentService, agenda_period
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User

SCHEDULED_AT = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)


def make_user(user_id: str, role: UserRole) -> User:
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        full_name=user_id,
        hashed_password="hashed",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def make_appointment(
    status: AppointmentStatus = AppointmentStatus.SCHEDULED,
) -> Appointment:
    return Appointment(
        id="appointment",
        patient_id="patient",
        doctor_id="doctor",
        created_by="attendant",
        scheduled_at=SCHEDULED_AT,
        status=status.value,
    )


class FakeUserRepository:
    def __init__(self, *users: User) -> None:
        self.users = {user.id: user for user in users}

    def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)


class FakeAppointmentRepository:
    def __init__(
        self,
        appointment: Appointment | None = None,
        *,
        conflict: bool = False,
    ) -> None:
        self.appointment = appointment
        self.conflict = conflict
        self.period: tuple[datetime, datetime] | None = None
        self.agenda_doctor_id: str | None = None

    def get_by_id(self, appointment_id: str) -> Appointment | None:
        return self.appointment

    def doctor_has_conflict(self, **kwargs: object) -> bool:
        return self.conflict

    def create(
        self,
        *,
        patient_id: str,
        doctor_id: str,
        created_by: str,
        scheduled_at: datetime,
    ) -> Appointment:
        return Appointment(
            id="appointment",
            patient_id=patient_id,
            doctor_id=doctor_id,
            created_by=created_by,
            scheduled_at=scheduled_at,
            status=AppointmentStatus.SCHEDULED.value,
        )

    def reschedule(
        self,
        appointment: Appointment,
        scheduled_at: datetime,
    ) -> Appointment:
        appointment.scheduled_at = scheduled_at
        return appointment

    def cancel(self, appointment: Appointment) -> Appointment:
        appointment.status = AppointmentStatus.CANCELLED.value
        return appointment

    def list_for_doctor_between(
        self,
        *,
        doctor_id: str,
        start: datetime,
        end: datetime,
    ) -> list[Appointment]:
        self.period = (start, end)
        self.agenda_doctor_id = doctor_id
        return []


def make_service(
    repository: FakeAppointmentRepository | None = None,
) -> AppointmentService:
    return AppointmentService(
        repository or FakeAppointmentRepository(),
        FakeUserRepository(
            make_user("patient", UserRole.PATIENT),
            make_user("doctor", UserRole.DOCTOR),
        ),
    )


def make_create(patient_id: str = "patient", doctor_id: str = "doctor"):
    return AppointmentCreate(
        patient_id=patient_id,
        doctor_id=doctor_id,
        scheduled_at=SCHEDULED_AT,
    )


def test_schedule_creates_appointment() -> None:
    appointment = make_service().schedule(
        current_user=make_user("attendant", UserRole.ATTENDANT),
        appointment_create=make_create(),
    )

    assert appointment.patient_id == "patient"
    assert appointment.doctor_id == "doctor"
    assert appointment.created_by == "attendant"


def test_schedule_rejects_patient_id_that_is_not_a_patient() -> None:
    with pytest.raises(InvalidPatientError):
        make_service().schedule(
            current_user=make_user("attendant", UserRole.ATTENDANT),
            appointment_create=make_create(patient_id="doctor"),
        )


def test_schedule_rejects_doctor_id_that_is_not_a_doctor() -> None:
    with pytest.raises(InvalidDoctorError):
        make_service().schedule(
            current_user=make_user("attendant", UserRole.ATTENDANT),
            appointment_create=make_create(doctor_id="patient"),
        )


def test_schedule_rejects_doctor_time_conflict() -> None:
    service = make_service(FakeAppointmentRepository(conflict=True))

    with pytest.raises(DoctorUnavailableError):
        service.schedule(
            current_user=make_user("attendant", UserRole.ATTENDANT),
            appointment_create=make_create(),
        )


def test_reschedule_changes_date() -> None:
    new_date = datetime(2026, 10, 15, 13, 0, tzinfo=UTC)
    service = make_service(FakeAppointmentRepository(make_appointment()))

    appointment = service.reschedule(
        appointment_id="appointment",
        scheduled_at=new_date,
    )

    assert appointment.scheduled_at == new_date


def test_reschedule_raises_when_appointment_does_not_exist() -> None:
    with pytest.raises(AppointmentNotFoundError):
        make_service().reschedule(
            appointment_id="missing",
            scheduled_at=SCHEDULED_AT,
        )


def test_cancel_rejects_appointment_that_is_not_scheduled() -> None:
    service = make_service(
        FakeAppointmentRepository(make_appointment(AppointmentStatus.COMPLETED))
    )

    with pytest.raises(AppointmentNotScheduledError):
        service.cancel(appointment_id="appointment")


@pytest.mark.parametrize(
    ("view", "expected_start", "expected_end"),
    [
        (AgendaView.DAY, date(2026, 10, 14), date(2026, 10, 15)),
        (AgendaView.WEEK, date(2026, 10, 12), date(2026, 10, 19)),
        (AgendaView.MONTH, date(2026, 10, 1), date(2026, 11, 1)),
    ],
)
def test_agenda_period(
    view: AgendaView,
    expected_start: date,
    expected_end: date,
) -> None:
    start, end = agenda_period(view, date(2026, 10, 14))

    assert start.date() == expected_start
    assert end.date() == expected_end
    assert start.utcoffset() is not None


def test_agenda_period_month_crosses_year() -> None:
    start, end = agenda_period(AgendaView.MONTH, date(2026, 12, 31))

    assert start.date() == date(2026, 12, 1)
    assert end.date() == date(2027, 1, 1)


def test_get_agenda_queries_requested_period() -> None:
    repository = FakeAppointmentRepository()

    agenda = make_service(repository).get_agenda(
        current_user=make_user("doctor", UserRole.DOCTOR),
        view=AgendaView.WEEK,
        day=date(2026, 10, 14),
        doctor_id="other-doctor",
    )

    assert repository.agenda_doctor_id == "doctor"
    assert repository.period == (agenda.start, agenda.end)
    assert agenda.view == AgendaView.WEEK
    assert agenda.appointments == []


def test_admin_gets_agenda_of_given_doctor() -> None:
    repository = FakeAppointmentRepository()

    make_service(repository).get_agenda(
        current_user=make_user("admin", UserRole.ADMIN),
        view=AgendaView.DAY,
        doctor_id="doctor",
    )

    assert repository.agenda_doctor_id == "doctor"


def test_admin_agenda_requires_doctor_id() -> None:
    with pytest.raises(AgendaDoctorRequiredError):
        make_service().get_agenda(
            current_user=make_user("admin", UserRole.ADMIN),
            view=AgendaView.DAY,
        )
