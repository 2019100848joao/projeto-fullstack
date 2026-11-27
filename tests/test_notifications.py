import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.core.database import Base
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.enums import UserRole
from app.modules.notifications.dependencies import get_notification_service
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.repository import EmailNotificationRepository
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User


class FakeEmailNotificationRepository:
    def __init__(self) -> None:
        self.items: list[EmailNotification] = []

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def create(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
        event_type: EmailEventType,
    ) -> EmailNotification:
        notification = EmailNotification(
            id=f"01K4EMAIL00000000000000000{len(self.items) + 1}",
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            event_type=event_type.value,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )
        self.items.append(notification)
        return notification

    def list_all(
        self,
        *,
        recipient_email: str | None = None,
    ) -> list[EmailNotification]:
        if recipient_email is None:
            return list(self.items)
        return [item for item in self.items if item.recipient_email == recipient_email]


def make_user(role: UserRole, email: str) -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email=email,
        full_name="Example User",
        hashed_password="not-returned",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def build_seeded_notification_service() -> NotificationService:
    service = NotificationService(FakeEmailNotificationRepository())
    service.record_registration_email(
        recipient_email="patient@example.com",
        full_name="Patient Example",
    )
    service.record_transition_requested_emails(
        requester_email="patient@example.com",
        requester_name="Patient Example",
        requested_role="doctor",
        admin_emails=["admin@clinic.com"],
    )
    return service


def test_list_emails_requires_authentication() -> None:
    response = TestClient(app).get("/notifications/emails")

    assert response.status_code == 401


def test_patient_lists_only_own_emails() -> None:
    service = build_seeded_notification_service()
    app.dependency_overrides[get_notification_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.PATIENT, "patient@example.com"
    )

    response = TestClient(app).get("/notifications/emails")

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert {item["recipient_email"] for item in response.json()} == {
        "patient@example.com"
    }


def test_admin_lists_all_emails() -> None:
    service = build_seeded_notification_service()
    app.dependency_overrides[get_notification_service] = lambda: service
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.ADMIN, "admin@clinic.com"
    )

    response = TestClient(app).get("/notifications/emails")

    assert response.status_code == 200
    assert len(response.json()) == 3


def test_email_repository_persists_and_filters_by_recipient() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        repository = EmailNotificationRepository(db)
        repository.create(
            recipient_email="patient@example.com",
            subject="Welcome",
            body="Welcome body",
            event_type=EmailEventType.USER_REGISTERED,
        )
        repository.create(
            recipient_email="admin@clinic.com",
            subject="Alert",
            body="Alert body",
            event_type=EmailEventType.ROLE_TRANSITION_ADMIN_ALERT,
        )

        assert len(repository.list_all()) == 2
        patient_emails = repository.list_all(recipient_email="patient@example.com")
        assert len(patient_emails) == 1
        assert len(patient_emails[0].id) == 26
