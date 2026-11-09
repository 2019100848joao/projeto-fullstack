from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.modules.appointments.enums import AppointmentStatus
from app.modules.appointments.models import Appointment
from app.modules.exams.enums import ExamStatus
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
        attended_patients = select(Appointment.patient_id).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.COMPLETED.value,
        )
        statement = self._filtered(patient_id=patient_id, status=status).where(
            Exam.patient_id.in_(attended_patients)
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

    def doctor_attended_patient(self, *, doctor_id: str, patient_id: str) -> bool:
        statement = select(Appointment.id).where(
            Appointment.doctor_id == doctor_id,
            Appointment.patient_id == patient_id,
            Appointment.status == AppointmentStatus.COMPLETED.value,
        )
        return self.db.scalar(statement.limit(1)) is not None

    def schedule(self, exam: Exam, scheduled_at: datetime) -> Exam:
        exam.scheduled_at = scheduled_at
        exam.status = ExamStatus.SCHEDULED.value
        return self._save(exam)

    def mark_performed(self, exam: Exam) -> Exam:
        exam.performed_at = datetime.now(UTC)
        exam.status = ExamStatus.PERFORMED.value
        return self._save(exam)

    def register_result(self, exam: Exam, result: str) -> Exam:
        exam.result = result
        exam.result_available_at = datetime.now(UTC)
        exam.status = ExamStatus.RESULT_AVAILABLE.value
        return self._save(exam)

    def _save(self, exam: Exam) -> Exam:
        self.db.commit()
        self.db.refresh(exam)
        return exam
