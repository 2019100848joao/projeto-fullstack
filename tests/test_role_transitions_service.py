from datetime import UTC, datetime

import pytest

from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.service import NotificationService
from app.modules.role_transitions.enums import TransitionStatus, TransitionTargetRole
from app.modules.role_transitions.exceptions import (
    InvalidRoleTransitionError,
    RoleTransitionAlreadyReviewedError,
)
from app.modules.role_transitions.models import RoleTransitionRequest
from app.modules.role_transitions.schemas import RoleTransitionCreate
from app.modules.role_transitions.service import RoleTransitionService


class FakeEmailNotificationRepository:
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


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}

    def get_by_id(self, user_id: str) -> User | None:
        return self.users.get(user_id)

    def list_all(self, *, role: UserRole | None = None) -> list[User]:
        items = list(self.users.values())
        if role is not None:
            items = [user for user in items if user.role == role.value]
        return items

    def update_role(self, user: User, role: UserRole) -> User:
        user.role = role.value
        return user


class FakeRoleTransitionRepository:
    def __init__(self) -> None:
        self.requests: dict[str, RoleTransitionRequest] = {}

    def create(
        self,
        *,
        user_id: str,
        requested_role: TransitionTargetRole,
    ) -> RoleTransitionRequest:
        req_id = f"01K4REQ0000000000000000000{len(self.requests) + 1}"
        request = RoleTransitionRequest(
            id=req_id,
            user_id=user_id,
            requested_role=requested_role.value,
            status=TransitionStatus.PENDING.value,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )
        self.requests[req_id] = request
        return request

    def get_by_id(self, request_id: str) -> RoleTransitionRequest | None:
        return self.requests.get(request_id)

    def list_all(
        self,
        *,
        status: TransitionStatus | None = None,
    ) -> list[RoleTransitionRequest]:
        items = list(self.requests.values())
        if status is not None:
            items = [item for item in items if item.status == status.value]
        return items

    def save(
        self,
        transition_request: RoleTransitionRequest,
    ) -> RoleTransitionRequest:
        self.requests[transition_request.id] = transition_request
        return transition_request


def make_user(user_id: str, email: str, name: str, role: UserRole) -> User:
    return User(
        id=user_id,
        email=email,
        full_name=name,
        hashed_password="hash",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def build_fixture() -> tuple[
    RoleTransitionService,
    NotificationService,
    User,
    User,
]:
    admin = make_user("01ADMIN", "admin@clinic.com", "Admin Base", UserRole.ADMIN)
    patient = make_user("01PATIENT", "user@clinic.com", "Paciente", UserRole.PATIENT)
    email_repo = FakeEmailNotificationRepository()
    notification_service = NotificationService(email_repo)  # type: ignore[arg-type]
    transition_service = RoleTransitionService(
        repository=FakeRoleTransitionRepository(),  # type: ignore[arg-type]
        user_repository=FakeUserRepository([admin, patient]),  # type: ignore[arg-type]
        notification_service=notification_service,
    )
    return transition_service, notification_service, admin, patient


def test_request_and_approve_transition_updates_role_and_records_emails() -> None:
    service, notifications, admin, patient = build_fixture()

    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )
    assert request.status == TransitionStatus.PENDING.value

    approved = service.approve_transition(admin_user=admin, request_id=request.id)
    assert approved.status == TransitionStatus.APPROVED.value
    assert patient.role == UserRole.DOCTOR.value

    all_emails = notifications.list_emails(
        requester_email=admin.email,
        is_admin=True,
    )
    assert [email.event_type for email in all_emails] == [
        EmailEventType.ROLE_TRANSITION_REQUESTED.value,
        EmailEventType.ROLE_TRANSITION_ADMIN_ALERT.value,
        EmailEventType.ROLE_TRANSITION_APPROVED.value,
    ]


def test_reject_transition_keeps_role_and_records_rejection_email() -> None:
    service, notifications, admin, patient = build_fixture()

    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.ATTENDANT),
    )
    rejected = service.reject_transition(admin_user=admin, request_id=request.id)

    assert rejected.status == TransitionStatus.REJECTED.value
    assert patient.role == UserRole.PATIENT.value

    patient_emails = notifications.list_emails(
        requester_email=patient.email,
        is_admin=False,
    )
    assert [email.event_type for email in patient_emails] == [
        EmailEventType.ROLE_TRANSITION_REQUESTED.value,
        EmailEventType.ROLE_TRANSITION_REJECTED.value,
    ]

    with pytest.raises(RoleTransitionAlreadyReviewedError):
        service.approve_transition(admin_user=admin, request_id=request.id)


def test_request_transition_rejects_same_role() -> None:
    service, _, _, patient = build_fixture()
    patient.role = UserRole.DOCTOR.value

    with pytest.raises(InvalidRoleTransitionError):
        service.request_transition(
            current_user=patient,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )
