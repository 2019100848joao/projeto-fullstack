from datetime import datetime

from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.exams.enums import ExamStatus
from app.modules.exams.exceptions import (
    ExamAccessDeniedError,
    ExamNotFoundError,
    InvalidExamStatusTransitionError,
)
from app.modules.exams.models import Exam
from app.modules.exams.repository import ExamRepository

STAFF_ROLES = {UserRole.ATTENDANT, UserRole.ADMIN}


class ExamService:
    def __init__(self, repository: ExamRepository) -> None:
        self.repository = repository

    def list_exams(
        self,
        *,
        current_user: User,
        status: ExamStatus | None = None,
        patient_id: str | None = None,
    ) -> list[Exam]:
        role = UserRole(current_user.role)

        if role in STAFF_ROLES:
            return self.repository.list(patient_id=patient_id, status=status)

        if role == UserRole.PATIENT:
            return self.repository.list(patient_id=current_user.id, status=status)

        return self.repository.list(
            patient_id=patient_id,
            status=status,
            attended_by_doctor_id=current_user.id,
        )

    def list_results(
        self,
        *,
        current_user: User,
        patient_id: str | None = None,
    ) -> list[Exam]:
        return self.list_exams(
            current_user=current_user,
            status=ExamStatus.RESULT_AVAILABLE,
            patient_id=patient_id,
        )

    def get_exam(self, *, current_user: User, exam_id: str) -> Exam:
        exam = self._get(exam_id)
        role = UserRole(current_user.role)

        if role in STAFF_ROLES:
            return exam

        if role == UserRole.PATIENT and exam.patient_id == current_user.id:
            return exam

        if role == UserRole.DOCTOR and self.repository.doctor_attended_patient(
            doctor_id=current_user.id,
            patient_id=exam.patient_id,
        ):
            return exam

        raise ExamAccessDeniedError

    def schedule(self, *, exam_id: str, scheduled_at: datetime) -> Exam:
        exam = self._get(exam_id)
        if exam.status not in {
            ExamStatus.REQUESTED.value,
            ExamStatus.SCHEDULED.value,
        }:
            raise InvalidExamStatusTransitionError

        return self.repository.schedule(exam, scheduled_at)

    def mark_performed(self, *, exam_id: str) -> Exam:
        exam = self._get(exam_id)
        if exam.status != ExamStatus.SCHEDULED.value:
            raise InvalidExamStatusTransitionError

        return self.repository.mark_performed(exam)

    def register_result(self, *, exam_id: str, result: str) -> Exam:
        exam = self._get(exam_id)
        if exam.status != ExamStatus.PERFORMED.value:
            raise InvalidExamStatusTransitionError

        return self.repository.register_result(exam, result)

    def _get(self, exam_id: str) -> Exam:
        exam = self.repository.get_by_id(exam_id)
        if exam is None:
            raise ExamNotFoundError

        return exam
