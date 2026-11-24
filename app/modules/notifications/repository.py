from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification


class EmailNotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

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
        self.db.commit()
        self.db.refresh(notification)
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
