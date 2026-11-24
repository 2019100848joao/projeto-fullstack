import os
from datetime import UTC, datetime

from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.notifications.dependencies import get_notification_service
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.service import NotificationService


class FakeEmailRepo:
    def __init__(self) -> None:
        self.items: list[EmailNotification] = []

    def create(
        self,
        *,
        recipient_email: str,
        subject: str,
        body: str,
        event_type: EmailEventType,
    ) -> EmailNotification:
        item = EmailNotification(
            id=f"01K4EMAIL00000000000000000{len(self.items) + 1}",
            recipient_email=recipient_email,
            subject=subject,
            body=body,
            event_type=event_type.value,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )
        self.items.append(item)
        return item

    def list_all(
        self,
        *,
        recipient_email: str | None = None,
    ) -> list[EmailNotification]:
        if recipient_email is None:
            return list(self.items)
        return [item for item in self.items if item.recipient_email == recipient_email]


def _make_user(role: UserRole, email: str) -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email=email,
        full_name="Test User",
        hashed_password="hashed",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_notification_service_handles_multiple_or_zero_admins() -> None:
    repo = FakeEmailRepo()
    service = NotificationService(repo)  # type: ignore[arg-type]

    no_admins = service.record_transition_requested_emails(
        requester_email="patient@clinic.com",
        requester_name="Paciente",
        requested_role="doctor",
        admin_emails=[],
    )
    assert len(no_admins) == 1
    assert no_admins[0].event_type == EmailEventType.ROLE_TRANSITION_REQUESTED.value

    two_admins = service.record_transition_requested_emails(
        requester_email="patient@clinic.com",
        requester_name="Paciente",
        requested_role="attendant",
        admin_emails=["admin1@clinic.com", "admin2@clinic.com"],
    )
    assert len(two_admins) == 3


def test_notifications_route_requires_auth_and_scopes_by_role() -> None:
    repo = FakeEmailRepo()
    service = NotificationService(repo)  # type: ignore[arg-type]
    service.record_registration_email(
        recipient_email="patient@clinic.com",
        full_name="Paciente",
    )
    service.record_transition_requested_emails(
        requester_email="patient@clinic.com",
        requester_name="Paciente",
        requested_role="doctor",
        admin_emails=["admin@clinic.com"],
    )

    client = TestClient(app)
    assert client.get("/notifications/emails").status_code == 401

    app.dependency_overrides[get_notification_service] = lambda: service
    try:
        app.dependency_overrides[get_current_user] = lambda: _make_user(
            UserRole.PATIENT, "patient@clinic.com"
        )
        patient_resp = client.get("/notifications/emails")
        assert patient_resp.status_code == 200
        assert len(patient_resp.json()) == 2
        assert all(
            item["recipient_email"] == "patient@clinic.com"
            for item in patient_resp.json()
        )

        app.dependency_overrides[get_current_user] = lambda: _make_user(
            UserRole.ADMIN, "admin@clinic.com"
        )
        admin_resp = client.get("/notifications/emails")
        assert admin_resp.status_code == 200
        assert len(admin_resp.json()) == 3
    finally:
        app.dependency_overrides.clear()
