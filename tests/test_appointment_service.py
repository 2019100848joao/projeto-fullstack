from datetime import UTC, datetime

import pytest

from app.modules.appointments.exceptions import (
    AppointmentConflictError,
    AppointmentPermissionError,
    DoctorNotFoundError,
    InvalidAppointmentTimeError,
    PatientNotFoundError,
)
from app.modules.appointments.models import Appointment
from app.modules.appointments.schemas import AppointmentCreate
from app.modules.appointments.service import AppointmentService
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User


class FakeAppointmentRepository:
    def __init__(
        self,
        *,
        doctor: User | None = None,
        patient: User | None = None,
        conflicting: bool = False,
    ) -> None:
        self.doctor = doctor
        self.patient = patient
        self.conflicting = conflicting

    def get_user_by_id(self, user_id: str) -> User | None:
        if self.doctor and user_id == self.doctor.id:
            return self.doctor
        if self.patient and user_id == self.patient.id:
            return self.patient
        return None

    def has_conflicting_appointment(
        self,
        *,
        doctor_id: str,
        starts_at: datetime,
        ends_at: datetime,
    ) -> bool:
        return self.conflicting

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
        return Appointment(
            id="01K5M9XG35G6YG4TVNRN8M7PRG",
            doctor_id=doctor_id,
            patient_id=patient_id,
            created_by_id=created_by_id,
            starts_at=starts_at,
            ends_at=ends_at,
            status="scheduled",
            reason=reason,
            created_at=datetime(2026, 9, 10, tzinfo=UTC),
        )


def test_create_appointment_requires_doctor_or_attendant() -> None:
    service = AppointmentService(FakeAppointmentRepository())

    with pytest.raises(AppointmentPermissionError):
        service.create_appointment(
            current_user=make_user(UserRole.PATIENT),
            appointment_create=make_appointment_create(),
        )


def test_create_appointment_requires_valid_time_range() -> None:
    doctor = make_user(UserRole.DOCTOR)
    patient = make_user(UserRole.PATIENT, user_id="01K5MA0T9NE7MD8WW2JY21S0MK")
    service = AppointmentService(
        FakeAppointmentRepository(doctor=doctor, patient=patient)
    )

    with pytest.raises(InvalidAppointmentTimeError):
        service.create_appointment(
            current_user=doctor,
            appointment_create=AppointmentCreate(
                doctor_id=doctor.id,
                patient_id=patient.id,
                starts_at=datetime(2026, 9, 10, 11, tzinfo=UTC),
                ends_at=datetime(2026, 9, 10, 10, tzinfo=UTC),
            ),
        )


def test_create_appointment_requires_doctor_user() -> None:
    patient = make_user(UserRole.PATIENT, user_id="01K5MA0T9NE7MD8WW2JY21S0MK")
    service = AppointmentService(FakeAppointmentRepository(patient=patient))

    with pytest.raises(DoctorNotFoundError):
        service.create_appointment(
            current_user=make_user(UserRole.ATTENDANT),
            appointment_create=make_appointment_create(patient_id=patient.id),
        )


def test_create_appointment_requires_patient_user() -> None:
    doctor = make_user(UserRole.DOCTOR)
    service = AppointmentService(FakeAppointmentRepository(doctor=doctor))

    with pytest.raises(PatientNotFoundError):
        service.create_appointment(
            current_user=doctor,
            appointment_create=make_appointment_create(doctor_id=doctor.id),
        )


def test_create_appointment_rejects_conflicting_appointment() -> None:
    doctor = make_user(UserRole.DOCTOR)
    patient = make_user(UserRole.PATIENT, user_id="01K5MA0T9NE7MD8WW2JY21S0MK")
    service = AppointmentService(
        FakeAppointmentRepository(doctor=doctor, patient=patient, conflicting=True)
    )

    with pytest.raises(AppointmentConflictError):
        service.create_appointment(
            current_user=doctor,
            appointment_create=make_appointment_create(
                doctor_id=doctor.id,
                patient_id=patient.id,
            ),
        )


def test_create_appointment_returns_scheduled_appointment() -> None:
    doctor = make_user(UserRole.DOCTOR)
    patient = make_user(UserRole.PATIENT, user_id="01K5MA0T9NE7MD8WW2JY21S0MK")
    service = AppointmentService(
        FakeAppointmentRepository(doctor=doctor, patient=patient)
    )

    appointment = service.create_appointment(
        current_user=make_user(UserRole.ATTENDANT),
        appointment_create=make_appointment_create(
            doctor_id=doctor.id,
            patient_id=patient.id,
            reason="Annual checkup",
        ),
    )

    assert appointment.doctor_id == doctor.id
    assert appointment.patient_id == patient.id
    assert appointment.status == "scheduled"
    assert appointment.reason == "Annual checkup"


def make_user(
    role: UserRole,
    *,
    user_id: str = "01K4SRY37DGE7K5YWWKNB0RESW",
) -> User:
    return User(
        id=user_id,
        email=f"{role.value}-{user_id}@example.com",
        full_name="Example User",
        hashed_password="not-returned",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 10, tzinfo=UTC),
    )


def make_appointment_create(
    *,
    doctor_id: str = "01K4SRY37DGE7K5YWWKNB0RESW",
    patient_id: str = "01K5MA0T9NE7MD8WW2JY21S0MK",
    reason: str | None = None,
) -> AppointmentCreate:
    return AppointmentCreate(
        doctor_id=doctor_id,
        patient_id=patient_id,
        starts_at=datetime(2026, 9, 10, 10, tzinfo=UTC),
        ends_at=datetime(2026, 9, 10, 10, 30, tzinfo=UTC),
        reason=reason,
    )
