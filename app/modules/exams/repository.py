from datetime import UTC, datetime

from sqlalchemy import Select, select, update
from sqlalchemy.orm import Session

from app.modules.exams.enums import ExamStatus
from app.modules.exams.exceptions import InvalidExamStatusTransitionError
from app.modules.exams.models import Exam


class ExamRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, exam_id: str) -> Exam | None:
        return self.db.get(Exam, exam_id)

    def list_all(
        self,
        *,
        patient_id: str | None = None,
        status: ExamStatus | None = None,
    ) -> list[Exam]:
        """All exams, for attendants and admins only."""
        return self._list(self._filtered(patient_id=patient_id, status=status))

    def list_for_patient(
        self,
        *,
        patient_id: str,
        status: ExamStatus | None = None,
    ) -> list[Exam]:
        return self._list(self._filtered(patient_id=patient_id, status=status))

    def list_for_doctor(
        self,
        *,
        doctor_id: str,
        patient_id: str | None = None,
        status: ExamStatus | None = None,
    ) -> list[Exam]:
        """Only the exams the doctor requested."""
        statement = self._filtered(patient_id=patient_id, status=status).where(
            Exam.doctor_id == doctor_id
        )
        return self._list(statement)

    def _filtered(
        self,
        *,
        patient_id: str | None,
        status: ExamStatus | None,
    ) -> Select[tuple[Exam]]:
        statement = select(Exam)
        if patient_id is not None:
            statement = statement.where(Exam.patient_id == patient_id)
        if status is not None:
            statement = statement.where(Exam.status == status.value)
        return statement

    def _list(self, statement: Select[tuple[Exam]]) -> list[Exam]:
        return list(self.db.scalars(statement.order_by(Exam.created_at.desc())))

    def schedule(self, exam: Exam, scheduled_at: datetime) -> Exam:
        return self._transition(
            exam,
            from_statuses=(ExamStatus.REQUESTED, ExamStatus.SCHEDULED),
            status=ExamStatus.SCHEDULED.value,
            scheduled_at=scheduled_at,
        )

    def mark_performed(self, exam: Exam) -> Exam:
        return self._transition(
            exam,
            from_statuses=(ExamStatus.SCHEDULED,),
            status=ExamStatus.PERFORMED.value,
            performed_at=datetime.now(UTC),
        )

    def register_result(self, exam: Exam, result: str) -> Exam:
        return self._transition(
            exam,
            from_statuses=(ExamStatus.PERFORMED,),
            status=ExamStatus.RESULT_AVAILABLE.value,
            result=result,
            result_available_at=datetime.now(UTC),
        )

    def _transition(
        self,
        exam: Exam,
        *,
        from_statuses: tuple[ExamStatus, ...],
        **values: object,
    ) -> Exam:
        # The status check runs in the UPDATE itself, so when two requests
        # move the same exam at once only the first one succeeds.
        result = self.db.execute(
            update(Exam)
            .where(
                Exam.id == exam.id,
                Exam.status.in_([status.value for status in from_statuses]),
            )
            .values(**values)
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise InvalidExamStatusTransitionError

        self.db.commit()
        self.db.refresh(exam)
        return exam
