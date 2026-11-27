from datetime import UTC, datetime

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.modules.appointments.models import Appointment
from app.modules.exams.enums import ExamStatus
from app.modules.exams.exceptions import InvalidExamStatusTransitionError
from app.modules.exams.models import Exam
from app.modules.exams.repository import ExamRepository

SCHEDULED_AT = datetime(2026, 10, 14, 13, 0, tzinfo=UTC)


def create_exam(
    db: Session,
    *,
    doctor_id: str = "doctor",
    status: ExamStatus = ExamStatus.REQUESTED,
) -> str:
    appointment = Appointment(
        patient_id="patient",
        doctor_id=doctor_id,
        created_by="attendant",
        scheduled_at=SCHEDULED_AT,
        status="completed",
    )
    db.add(appointment)
    db.flush()
    exam = Exam(
        appointment_id=appointment.id,
        patient_id="patient",
        doctor_id=doctor_id,
        name=f"Exam by {doctor_id}",
        status=status.value,
    )
    db.add(exam)
    db.commit()
    return exam.id


def test_exam_goes_through_all_statuses(engine: Engine) -> None:
    with Session(engine) as db:
        repository = ExamRepository(db)
        exam = repository.get_by_id(create_exam(db))

        repository.schedule(exam, SCHEDULED_AT)
        repository.mark_performed(exam)
        repository.register_result(exam, "Normal")

        assert exam.status == ExamStatus.RESULT_AVAILABLE.value
        assert exam.result == "Normal"
        assert exam.performed_at is not None
        assert exam.result_available_at is not None


def test_invalid_transition_is_rejected(engine: Engine) -> None:
    with Session(engine) as db:
        repository = ExamRepository(db)
        exam = repository.get_by_id(create_exam(db))

        with pytest.raises(InvalidExamStatusTransitionError):
            repository.register_result(exam, "Normal")

        db.refresh(exam)
        assert exam.status == ExamStatus.REQUESTED.value
        assert exam.result is None


def test_concurrent_results_do_not_overwrite_each_other(engine: Engine) -> None:
    with Session(engine) as db:
        exam_id = create_exam(db, status=ExamStatus.PERFORMED)

    with Session(engine) as first, Session(engine) as second:
        # Both requests load the exam while it is still performed.
        first_exam = first.get(Exam, exam_id)
        second_exam = second.get(Exam, exam_id)

        ExamRepository(first).register_result(first_exam, "First")

        with pytest.raises(InvalidExamStatusTransitionError):
            ExamRepository(second).register_result(second_exam, "Second")

    with Session(engine) as db:
        assert db.get(Exam, exam_id).result == "First"


def test_doctor_only_lists_exams_they_requested(engine: Engine) -> None:
    with Session(engine) as db:
        own_exam_id = create_exam(db, doctor_id="doctor")
        create_exam(db, doctor_id="other-doctor")

        exams = ExamRepository(db).list_for_doctor(doctor_id="doctor")

        assert [exam.id for exam in exams] == [own_exam_id]
