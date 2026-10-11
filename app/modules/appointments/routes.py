from fastapi import APIRouter, HTTPException, status

from app.modules.appointments.dependencies import AppointmentServiceDep
from app.modules.appointments.exceptions import (
    AppointmentConflictError,
    AppointmentPermissionError,
    DoctorNotFoundError,
    InvalidAppointmentTimeError,
    PatientNotFoundError,
)
from app.modules.appointments.models import Appointment
from app.modules.appointments.schemas import AppointmentCreate, AppointmentRead
from app.modules.auth.dependencies import CurrentUserDep

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentRead, status_code=status.HTTP_201_CREATED)
def create_appointment(
    appointment_create: AppointmentCreate,
    current_user: CurrentUserDep,
    appointment_service: AppointmentServiceDep,
) -> Appointment:
    try:
        return appointment_service.create_appointment(
            current_user=current_user,
            appointment_create=appointment_create,
        )
    except AppointmentPermissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only doctors and attendants can create appointments",
        ) from exc
    except DoctorNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Doctor not found",
        ) from exc
    except PatientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        ) from exc
    except InvalidAppointmentTimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Appointment start time must be before end time",
        ) from exc
    except AppointmentConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doctor already has an appointment at this time",
        ) from exc
