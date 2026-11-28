from fastapi import APIRouter

from app.modules.auth.dependencies import CurrentUserDep
from app.modules.auth.enums import UserRole
from app.modules.notifications.dependencies import NotificationServiceDep
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.schemas import EmailNotificationRead

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("/emails", response_model=list[EmailNotificationRead])
def list_emails(
    current_user: CurrentUserDep,
    notification_service: NotificationServiceDep,
) -> list[EmailNotification]:
    return notification_service.list_emails(
        requester_email=current_user.email,
        is_admin=current_user.role == UserRole.ADMIN.value,
    )
