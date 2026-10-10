from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.modules.appointments.dependencies import (
    DoctorOrAdminUserDep,
    SchedulerUserDep,
    get_appointment_service,
)
from app.modules.appointments.enums import AgendaView
from app.modules.appointments.exceptions import (
    AgendaDoctorRequiredError,
    AppointmentNotFoundError,
    AppointmentNotScheduledError,
    DoctorUnavailableError,
    InvalidDoctorError,
    InvalidPatientError,
)
from app.modules.appointments.models import Appointment
from app.modules.appointments.schemas import (
    AgendaRead,
    AppointmentCreate,
    AppointmentRead,
    AppointmentReschedule,
)
from app.modules.appointments.service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["appointments"])

AppointmentServiceDep = Annotated[
    AppointmentService,
    Depends(get_appointment_service),
]

NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Appointment not found",
)
NOT_SCHEDULED = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Appointment is not in scheduled status",
)
DOCTOR_UNAVAILABLE = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail="Doctor already has an appointment at this time",
)


@router.post(
    "",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Schedule an appointment (attendant, admin)",
)
def schedule_appointment(
    appointment_create: AppointmentCreate,
    current_user: SchedulerUserDep,
    service: AppointmentServiceDep,
) -> Appointment:
    try:
        return service.schedule(
            current_user=current_user,
            appointment_create=appointment_create,
        )
    except InvalidPatientError as exc:
        raise HTTPException(
            status_code=422,
            detail="patient_id must reference a user with the patient role",
        ) from exc
    except InvalidDoctorError as exc:
        raise HTTPException(
            status_code=422,
            detail="doctor_id must reference a user with the doctor role",
        ) from exc
    except DoctorUnavailableError as exc:
        raise DOCTOR_UNAVAILABLE from exc


@router.get(
    "",
    response_model=list[AppointmentRead],
    summary="List appointments (attendant, admin)",
)
def list_appointments(
    current_user: SchedulerUserDep,
    service: AppointmentServiceDep,
    doctor_id: str | None = None,
    patient_id: str | None = None,
) -> list[Appointment]:
    return service.list_appointments(doctor_id=doctor_id, patient_id=patient_id)


@router.get(
    "/agenda",
    response_model=AgendaRead,
    summary="Doctor agenda by day, week or month (doctor, admin)",
)
def read_agenda(
    current_user: DoctorOrAdminUserDep,
    service: AppointmentServiceDep,
    view: AgendaView = AgendaView.DAY,
    day: Annotated[
        date | None,
        Query(alias="date", description="Reference date. Defaults to today."),
    ] = None,
    doctor_id: Annotated[
        str | None,
        Query(description="Required for admin. Doctors always get their own."),
    ] = None,
) -> AgendaRead:
    try:
        return service.get_agenda(
            current_user=current_user,
            view=view,
            day=day,
            doctor_id=doctor_id,
        )
    except AgendaDoctorRequiredError as exc:
        raise HTTPException(
            status_code=422,
            detail="doctor_id is required for admin users",
        ) from exc


@router.patch(
    "/{appointment_id}",
    response_model=AppointmentRead,
    summary="Reschedule an appointment (attendant, admin)",
)
def reschedule_appointment(
    appointment_id: str,
    reschedule: AppointmentReschedule,
    current_user: SchedulerUserDep,
    service: AppointmentServiceDep,
) -> Appointment:
    try:
        return service.reschedule(
            appointment_id=appointment_id,
            scheduled_at=reschedule.scheduled_at,
        )
    except AppointmentNotFoundError as exc:
        raise NOT_FOUND from exc
    except AppointmentNotScheduledError as exc:
        raise NOT_SCHEDULED from exc
    except DoctorUnavailableError as exc:
        raise DOCTOR_UNAVAILABLE from exc


@router.post(
    "/{appointment_id}/cancel",
    response_model=AppointmentRead,
    summary="Cancel an appointment (attendant, admin)",
)
def cancel_appointment(
    appointment_id: str,
    current_user: SchedulerUserDep,
    service: AppointmentServiceDep,
) -> Appointment:
    try:
        return service.cancel(appointment_id=appointment_id)
    except AppointmentNotFoundError as exc:
        raise NOT_FOUND from exc
    except AppointmentNotScheduledError as exc:
        raise NOT_SCHEDULED from exc
