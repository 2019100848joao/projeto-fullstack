from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.appointments.enums import AppointmentStatus
from app.modules.appointments.models import Appointment
from app.modules.auth.models import User


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_user_by_id(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

    def has_conflicting_appointment(
        self,
        *,
        doctor_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        statement = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status == AppointmentStatus.SCHEDULED.value,
            Appointment.starts_at < ends_at,
            Appointment.ends_at > starts_at,
        )
        return self.db.scalar(statement) is not None

    def create_appointment(
        self,
        *,
        doctor_id: str,
        patient_id: str,
        created_by_id: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str | None,
    ) -> Appointment:
        appointment = Appointment(
            doctor_id=doctor_id,
            patient_id=patient_id,
            created_by_id=created_by_id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=reason,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment
