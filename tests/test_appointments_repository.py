from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import Engine, create_engine, func, select
from sqlalchemy.orm import Session

from app.core.database import Base
from app.modules.appointments.enums import AppointmentStatus
from app.modules.appointments.exceptions import (
    AppointmentNotScheduledError,
    DoctorUnavailableError,
)
from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import AppointmentRepository
from app.modules.auth.enums import UserRole
from app.modules.exams.models import Exam
from app.modules.users.models import User

SCHEDULED_AT = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    # A file database, so two sessions have separate connections, as two
    # concurrent requests would.
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'clinic.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                full_name=user_id,
                hashed_password="hashed",
                role=role.value,
            )
            for user_id, role in (
                ("patient", UserRole.PATIENT),
                ("doctor", UserRole.DOCTOR),
                ("attendant", UserRole.ATTENDANT),
            )
        )
        db.commit()
    yield engine
    engine.dispose()


def create_appointment(db: Session) -> Appointment:
    return AppointmentRepository(db).create(
        patient_id="patient",
        doctor_id="doctor",
        created_by="attendant",
        scheduled_at=SCHEDULED_AT,
    )


def test_database_rejects_second_appointment_in_the_same_slot(engine: Engine) -> None:
    with Session(engine) as db:
        create_appointment(db)

        # Calls the repository directly, as a request that passed the service
        # check before the first one was saved.
        with pytest.raises(DoctorUnavailableError):
            create_appointment(db)

        assert db.scalar(select(func.count()).select_from(Appointment)) == 1


def test_cancelled_appointment_frees_the_slot(engine: Engine) -> None:
    with Session(engine) as db:
        repository = AppointmentRepository(db)
        repository.cancel(create_appointment(db))

        appointment = create_appointment(db)

        assert appointment.status == AppointmentStatus.SCHEDULED.value


def test_reschedule_into_a_taken_slot_is_rejected(engine: Engine) -> None:
    other_time = datetime(2026, 10, 14, 14, 0, tzinfo=UTC)
    with Session(engine) as db:
        repository = AppointmentRepository(db)
        create_appointment(db)
        second = repository.create(
            patient_id="patient",
            doctor_id="doctor",
            created_by="attendant",
            scheduled_at=other_time,
        )

        with pytest.raises(DoctorUnavailableError):
            repository.reschedule(second, SCHEDULED_AT)

        db.refresh(second)
        assert second.scheduled_at.replace(tzinfo=UTC) == other_time


def test_duplicate_attendance_request_does_not_duplicate_exams(engine: Engine) -> None:
    with Session(engine) as db:
        appointment_id = create_appointment(db).id

    with Session(engine) as first, Session(engine) as second:
        # Both requests load the appointment while it is still scheduled.
        first_appointment = first.get(Appointment, appointment_id)
        second_appointment = second.get(Appointment, appointment_id)
        assert first_appointment.status == AppointmentStatus.SCHEDULED.value
        assert second_appointment.status == AppointmentStatus.SCHEDULED.value

        AppointmentRepository(first).register_attendance(
            first_appointment,
            observations="First",
            consultation_info=None,
            exam_names=["Blood count"],
        )

        with pytest.raises(AppointmentNotScheduledError):
            AppointmentRepository(second).register_attendance(
                second_appointment,
                observations="Second",
                consultation_info=None,
                exam_names=["Blood count"],
            )

    with Session(engine) as db:
        appointment = db.get(Appointment, appointment_id)
        assert appointment.status == AppointmentStatus.COMPLETED.value
        assert appointment.observations == "First"
        assert db.scalar(select(func.count()).select_from(Exam)) == 1


def test_completed_appointment_cannot_be_cancelled_by_a_stale_request(
    engine: Engine,
) -> None:
    with Session(engine) as db:
        appointment_id = create_appointment(db).id

    with Session(engine) as first, Session(engine) as second:
        stale = second.get(Appointment, appointment_id)
        AppointmentRepository(first).register_attendance(
            first.get(Appointment, appointment_id),
            observations=None,
            consultation_info=None,
            exam_names=[],
        )

        with pytest.raises(AppointmentNotScheduledError):
            AppointmentRepository(second).cancel(stale)

    with Session(engine) as db:
        status = db.get(Appointment, appointment_id).status
        assert status == AppointmentStatus.COMPLETED.value
