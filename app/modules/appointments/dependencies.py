from typing import Annotated

from fastapi import Depends

from app.modules.appointments.repository import AppointmentRepository
from app.modules.appointments.service import AppointmentService
from app.modules.auth.dependencies import DbSession, require_roles
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository


def get_appointment_service(db: DbSession) -> AppointmentService:
    return AppointmentService(AppointmentRepository(db), UserRepository(db))


SchedulerUserDep = Annotated[
    User,
    Depends(require_roles(UserRole.ATTENDANT, UserRole.ADMIN)),
]
DoctorOrAdminUserDep = Annotated[
    User,
    Depends(require_roles(UserRole.DOCTOR, UserRole.ADMIN)),
]
