from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.appointments.enums import AppointmentStatus
from app.modules.appointments.models import Appointment
from app.modules.exams.enums import ExamStatus
from app.modules.exams.models import Exam
from app.modules.users.repository import UserRepository

SCHEDULED_AT = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)


def add_appointment(db: Session, status: AppointmentStatus) -> Appointment:
    appointment = Appointment(
        patient_id="patient",
        doctor_id="doctor",
        created_by="attendant",
        scheduled_at=SCHEDULED_AT,
        status=status.value,
    )
    db.add(appointment)
    db.flush()
    return appointment


def test_doctor_without_appointments_or_exams_has_no_open_work(engine: Engine) -> None:
    with Session(engine) as db:
        assert UserRepository(db).has_open_doctor_work("doctor") is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (AppointmentStatus.SCHEDULED, True),
        (AppointmentStatus.COMPLETED, False),
        (AppointmentStatus.CANCELLED, False),
        (AppointmentStatus.NO_SHOW, False),
    ],
)
def test_only_scheduled_appointments_count_as_open_work(
    engine: Engine,
    status: AppointmentStatus,
    expected: bool,
) -> None:
    with Session(engine) as db:
        add_appointment(db, status)

        assert UserRepository(db).has_open_doctor_work("doctor") is expected
        assert UserRepository(db).has_open_doctor_work("other-doctor") is False


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (ExamStatus.REQUESTED, True),
        (ExamStatus.SCHEDULED, True),
        (ExamStatus.PERFORMED, True),
        (ExamStatus.RESULT_AVAILABLE, False),
    ],
)
def test_exams_without_result_count_as_open_work(
    engine: Engine,
    status: ExamStatus,
    expected: bool,
) -> None:
    with Session(engine) as db:
        appointment = add_appointment(db, AppointmentStatus.COMPLETED)
        db.add(
            Exam(
                appointment_id=appointment.id,
                patient_id="patient",
                doctor_id="doctor",
                name="Hemograma",
                status=status.value,
            )
        )
        db.flush()

        assert UserRepository(db).has_open_doctor_work("doctor") is expected
