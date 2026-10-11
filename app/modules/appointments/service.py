from datetime import UTC

from app.modules.appointments.exceptions import (
    AppointmentConflictError,
    AppointmentPermissionError,
    DoctorNotFoundError,
    InvalidAppointmentTimeError,
    PatientNotFoundError,
)
from app.modules.appointments.models import Appointment
from app.modules.appointments.repository import AppointmentRepository
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.auth.permissions import PermissionService


class AppointmentService:
    def __init__(
        self,
        repository: AppointmentRepository,
        permissions: PermissionService | None = None,
    ) -> None:
        self.repository = repository
        self.permissions = permissions or PermissionService()

    def create_appointment(
        self,
        *,
        current_user: User,
        appointment_create: AppointmentCreate,
    ) -> Appointment:
        if not self.permissions.can_create_appointment(current_user):
            raise AppointmentPermissionError

        if appointment_create.starts_at >= appointment_create.ends_at:
            raise InvalidAppointmentTimeError

        starts_at = appointment_create.starts_at.astimezone(UTC)
        ends_at = appointment_create.ends_at.astimezone(UTC)

        doctor = self.repository.get_user_by_id(appointment_create.doctor_id)
        if doctor is None or doctor.role != UserRole.DOCTOR.value:
            raise DoctorNotFoundError

        patient = self.repository.get_user_by_id(appointment_create.patient_id)
        if patient is None or patient.role != UserRole.PATIENT.value:
            raise PatientNotFoundError

        if self.repository.has_conflicting_appointment(
            doctor_id=appointment_create.doctor_id,
            starts_at=starts_at,
            ends_at=ends_at,
        ):
            raise AppointmentConflictError

        return self.repository.create_appointment(
            doctor_id=appointment_create.doctor_id,
            patient_id=appointment_create.patient_id,
            created_by_id=current_user.id,
            starts_at=starts_at,
            ends_at=ends_at,
            reason=appointment_create.reason,
        )
