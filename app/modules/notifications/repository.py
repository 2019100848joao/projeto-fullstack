from sqlalchemy import select

from app.core.database import SqlRepository
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification


class EmailNotificationRepository(SqlRepository):
    def create(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
        event_type: EmailEventType,
    ) -> EmailNotification:
        notification = EmailNotification(
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            event_type=event_type.value,
        )
        self.db.add(notification)
        self.db.flush()
        return notification

    def list_all(
        self,
        *,
        recipient_email: str | None = None,
    ) -> list[EmailNotification]:
        statement = select(EmailNotification).order_by(
            EmailNotification.created_at.desc()
        )
        if recipient_email is not None:
            statement = statement.where(
                EmailNotification.recipient_email == recipient_email
            )
        return list(self.db.scalars(statement))
