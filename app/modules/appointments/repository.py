from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.modules.appointments.enums import AppointmentStatus
from app.modules.appointments.exceptions import (
    AppointmentNotScheduledError,
    DoctorUnavailableError,
)
from app.modules.appointments.models import Appointment
from app.modules.exams.models import Exam


class AppointmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, appointment_id: str) -> Appointment | None:
        return self.db.get(Appointment, appointment_id)

    def list_all(
        self,
        *,
        doctor_id: str | None = None,
        patient_id: str | None = None,
    ) -> list[Appointment]:
        statement = select(Appointment).order_by(Appointment.scheduled_at)
        if doctor_id is not None:
            statement = statement.where(Appointment.doctor_id == doctor_id)
        if patient_id is not None:
            statement = statement.where(Appointment.patient_id == patient_id)
        return list(self.db.scalars(statement))

    def list_for_doctor_between(
        self,
        *,
        doctor_id: str,
        start: datetime,
        end: datetime,
    ) -> list[Appointment]:
        statement = (
            select(Appointment)
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.scheduled_at >= start,
                Appointment.scheduled_at < end,
                Appointment.status != AppointmentStatus.CANCELLED.value,
            )
            .order_by(Appointment.scheduled_at)
        )
        return list(self.db.scalars(statement))

    def doctor_has_conflict(
        self,
        *,
        doctor_id: str,
        scheduled_at: datetime,
        ignore_appointment_id: str | None = None,
    ) -> bool:
        statement = select(Appointment.id).where(
            Appointment.doctor_id == doctor_id,
            Appointment.scheduled_at == scheduled_at,
            Appointment.status != AppointmentStatus.CANCELLED.value,
        )
        if ignore_appointment_id is not None:
            statement = statement.where(Appointment.id != ignore_appointment_id)
        return self.db.scalar(statement) is not None

    def create(
        self,
        *,
        patient_id: str,
        doctor_id: str,
        created_by: str,
        scheduled_at: datetime,
    ) -> Appointment:
        appointment = Appointment(
            patient_id=patient_id,
            doctor_id=doctor_id,
            created_by=created_by,
            scheduled_at=scheduled_at,
        )
        with self._doctor_slot(doctor_id=doctor_id, scheduled_at=scheduled_at):
            self.db.add(appointment)
            self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def reschedule(
        self,
        appointment: Appointment,
        scheduled_at: datetime,
    ) -> Appointment:
        with self._doctor_slot(
            doctor_id=appointment.doctor_id,
            scheduled_at=scheduled_at,
            ignore_appointment_id=appointment.id,
        ):
            self._update_if_scheduled(appointment, scheduled_at=scheduled_at)
            self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def cancel(self, appointment: Appointment) -> Appointment:
        self._update_if_scheduled(
            appointment,
            status=AppointmentStatus.CANCELLED.value,
        )
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def register_attendance(
        self,
        appointment: Appointment,
        *,
        observations: str | None,
        consultation_info: str | None,
        exam_names: list[str],
    ) -> Appointment:
        self._update_if_scheduled(
            appointment,
            status=AppointmentStatus.COMPLETED.value,
            observations=observations,
            consultation_info=consultation_info,
            attended_at=datetime.now(UTC),
        )
        for name in exam_names:
            self.db.add(
                Exam(
                    appointment_id=appointment.id,
                    patient_id=appointment.patient_id,
                    doctor_id=appointment.doctor_id,
                    name=name,
                )
            )
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def _update_if_scheduled(self, appointment: Appointment, **values: object) -> None:
        # The status check runs in the UPDATE itself, so when two requests
        # change the same appointment at once only the first one succeeds.
        result = self.db.execute(
            update(Appointment)
            .where(
                Appointment.id == appointment.id,
                Appointment.status == AppointmentStatus.SCHEDULED.value,
            )
            .values(**values)
        )
        if result.rowcount != 1:
            self.db.rollback()
            raise AppointmentNotScheduledError

    @contextmanager
    def _doctor_slot(
        self,
        *,
        doctor_id: str,
        scheduled_at: datetime,
        ignore_appointment_id: str | None = None,
    ) -> Iterator[None]:
        # The unique index ux_appointments_doctor_active_slot rejects a second
        # appointment for the same doctor and time even when two requests pass
        # the service check at the same moment.
        try:
            yield
        except IntegrityError as exc:
            self.db.rollback()
            if self.doctor_has_conflict(
                doctor_id=doctor_id,
                scheduled_at=scheduled_at,
                ignore_appointment_id=ignore_appointment_id,
            ):
                raise DoctorUnavailableError from exc
            raise
