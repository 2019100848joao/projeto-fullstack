from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.auth.repository import UserRepository
from app.modules.notifications.dependencies import NotificationServiceDep
from app.modules.role_transitions.repository import RoleTransitionRepository
from app.modules.role_transitions.service import RoleTransitionService

DbSession = Annotated[Session, Depends(get_db)]


def get_role_transition_service(
    db: DbSession,
    notification_service: NotificationServiceDep,
) -> RoleTransitionService:
    return RoleTransitionService(
        repository=RoleTransitionRepository(db),
        user_repository=UserRepository(db),
        notification_service=notification_service,
    )


RoleTransitionServiceDep = Annotated[
    RoleTransitionService,
    Depends(get_role_transition_service),
]
