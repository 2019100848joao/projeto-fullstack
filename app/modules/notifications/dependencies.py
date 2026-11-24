from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.notifications.repository import EmailNotificationRepository
from app.modules.notifications.service import NotificationService

DbSession = Annotated[Session, Depends(get_db)]


def get_notification_service(db: DbSession) -> NotificationService:
    return NotificationService(EmailNotificationRepository(db))


NotificationServiceDep = Annotated[
    NotificationService,
    Depends(get_notification_service),
]
