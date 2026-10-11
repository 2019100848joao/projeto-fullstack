from typing import Annotated

from fastapi import Depends

from app.modules.appointments.repository import AppointmentRepository
from app.modules.appointments.service import AppointmentService
from app.modules.auth.dependencies import DbSession
from app.modules.auth.permissions import PermissionService


def get_appointment_service(db: DbSession) -> AppointmentService:
    return AppointmentService(AppointmentRepository(db), PermissionService())


AppointmentServiceDep = Annotated[AppointmentService, Depends(get_appointment_service)]
