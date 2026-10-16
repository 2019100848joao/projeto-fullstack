from datetime import UTC, datetime

import pytest

from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.exams.enums import ExamStatus
from app.modules.exams.exceptions import (
    ExamAccessDeniedError,
    ExamNotFoundError,
    InvalidExamStatusTransitionError,
)
from app.modules.exams.models import Exam
from app.modules.exams.service import ExamService

SCHEDULED_AT = datetime(2026, 10, 16, 11, 0, tzinfo=UTC)


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


def make_exam(status: ExamStatus = ExamStatus.REQUESTED) -> Exam:
    return Exam(
        id="exam",
        appointment_id="appointment",
        patient_id="patient",
        doctor_id="doctor",
        name="Blood count",
        status=status.value,
    )


class FakeExamRepository:
    def __init__(
        self,
        exam: Exam | None = None,
        *,
        attended: bool = False,
    ) -> None:
        self.exam = exam
        self.attended = attended
        self.list_filters: dict[str, object] | None = None

    def get_by_id(self, exam_id: str) -> Exam | None:
        return self.exam

    def list(self, **filters: object) -> list[Exam]:
        self.list_filters = filters
        return []

    def doctor_attended_patient(self, *, doctor_id: str, patient_id: str) -> bool:
        return self.attended

    def schedule(self, exam: Exam, scheduled_at: datetime) -> Exam:
        exam.scheduled_at = scheduled_at
        exam.status = ExamStatus.SCHEDULED.value
        return exam

    def mark_performed(self, exam: Exam) -> Exam:
        exam.status = ExamStatus.PERFORMED.value
        return exam

    def register_result(self, exam: Exam, result: str) -> Exam:
        exam.result = result
        exam.status = ExamStatus.RESULT_AVAILABLE.value
        return exam


def test_exam_goes_through_all_statuses() -> None:
    service = ExamService(FakeExamRepository(make_exam()))

    assert service.schedule(exam_id="exam", scheduled_at=SCHEDULED_AT).status == (
        "scheduled"
    )
    assert service.mark_performed(exam_id="exam").status == "performed"

    exam = service.register_result(exam_id="exam", result="Normal")

    assert exam.status == "result_available"
    assert exam.result == "Normal"


def test_perform_rejects_exam_that_is_not_scheduled() -> None:
    service = ExamService(FakeExamRepository(make_exam()))

    with pytest.raises(InvalidExamStatusTransitionError):
        service.mark_performed(exam_id="exam")


def test_result_rejects_exam_that_is_not_performed() -> None:
    service = ExamService(FakeExamRepository(make_exam(ExamStatus.SCHEDULED)))

    with pytest.raises(InvalidExamStatusTransitionError):
        service.register_result(exam_id="exam", result="Normal")


def test_schedule_rejects_performed_exam() -> None:
    service = ExamService(FakeExamRepository(make_exam(ExamStatus.PERFORMED)))

    with pytest.raises(InvalidExamStatusTransitionError):
        service.schedule(exam_id="exam", scheduled_at=SCHEDULED_AT)


def test_schedule_raises_when_exam_does_not_exist() -> None:
    with pytest.raises(ExamNotFoundError):
        ExamService(FakeExamRepository()).schedule(
            exam_id="missing",
            scheduled_at=SCHEDULED_AT,
        )


def test_patient_only_lists_own_exams() -> None:
    repository = FakeExamRepository()

    ExamService(repository).list_exams(
        current_user=make_user("patient", UserRole.PATIENT),
        patient_id="other-patient",
    )

    assert repository.list_filters == {"patient_id": "patient", "status": None}


def test_doctor_only_lists_exams_of_attended_patients() -> None:
    repository = FakeExamRepository()

    ExamService(repository).list_results(
        current_user=make_user("doctor", UserRole.DOCTOR),
    )

    assert repository.list_filters == {
        "patient_id": None,
        "status": ExamStatus.RESULT_AVAILABLE,
        "attended_by_doctor_id": "doctor",
    }


def test_admin_lists_exams_of_any_patient() -> None:
    repository = FakeExamRepository()

    ExamService(repository).list_exams(
        current_user=make_user("admin", UserRole.ADMIN),
        patient_id="patient",
    )

    assert repository.list_filters == {"patient_id": "patient", "status": None}


def test_admin_can_read_any_exam() -> None:
    service = ExamService(FakeExamRepository(make_exam()))

    exam = service.get_exam(
        current_user=make_user("admin", UserRole.ADMIN),
        exam_id="exam",
    )

    assert exam.id == "exam"


def test_patient_can_read_own_exam() -> None:
    service = ExamService(FakeExamRepository(make_exam()))

    exam = service.get_exam(
        current_user=make_user("patient", UserRole.PATIENT),
        exam_id="exam",
    )

    assert exam.id == "exam"


def test_patient_cannot_read_exam_of_another_patient() -> None:
    service = ExamService(FakeExamRepository(make_exam()))

    with pytest.raises(ExamAccessDeniedError):
        service.get_exam(
            current_user=make_user("other-patient", UserRole.PATIENT),
            exam_id="exam",
        )


def test_doctor_can_read_exam_of_attended_patient() -> None:
    service = ExamService(FakeExamRepository(make_exam(), attended=True))

    exam = service.get_exam(
        current_user=make_user("doctor", UserRole.DOCTOR),
        exam_id="exam",
    )

    assert exam.id == "exam"


def test_doctor_cannot_read_exam_of_patient_not_attended() -> None:
    service = ExamService(FakeExamRepository(make_exam(), attended=False))

    with pytest.raises(ExamAccessDeniedError):
        service.get_exam(
            current_user=make_user("doctor", UserRole.DOCTOR),
            exam_id="exam",
        )
