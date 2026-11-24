from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.modules.notifications.enums import EmailEventType


class EmailNotificationRead(BaseModel):
    id: str
    recipient_email: EmailStr
    subject: str
    body: str
    event_type: EmailEventType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
