from datetime import UTC, datetime

from sqlalchemy import select
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

    def list(
        self,
        *,
        patient_id: str | None = None,
        status: ExamStatus | None = None,
        attended_by_doctor_id: str | None = None,
    ) -> list[Exam]:
        statement = select(Exam).order_by(Exam.created_at.desc())
        if patient_id is not None:
            statement = statement.where(Exam.patient_id == patient_id)
        if status is not None:
            statement = statement.where(Exam.status == status.value)
        if attended_by_doctor_id is not None:
            statement = statement.where(
                Exam.patient_id.in_(
                    select(Appointment.patient_id).where(
                        Appointment.doctor_id == attended_by_doctor_id,
                        Appointment.status == AppointmentStatus.COMPLETED.value,
                    )
                )
            )
        return list(self.db.scalars(statement))

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
