from datetime import UTC, datetime

import pytest

from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import UserNotFoundError
from app.modules.auth.models import User
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.service import NotificationService
from app.modules.role_transitions.enums import TransitionStatus, TransitionTargetRole
from app.modules.role_transitions.exceptions import (
    InvalidRoleTransitionError,
    PendingRoleTransitionExistsError,
    RoleTransitionAlreadyReviewedError,
    RoleTransitionNotFoundError,
    RoleTransitionPermissionError,
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

    def get_pending_by_user_id(self, user_id: str) -> RoleTransitionRequest | None:
        for item in self.requests.values():
            if (
                item.user_id == user_id
                and item.status == TransitionStatus.PENDING.value
            ):
                return item
        return None

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


def make_user(
    user_id: str,
    email: str,
    name: str,
    role: UserRole,
    *,
    is_active: bool = True,
) -> User:
    return User(
        id=user_id,
        email=email,
        full_name=name,
        hashed_password="hash",
        role=role.value,
        is_active=is_active,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def build_fixture() -> tuple[
    RoleTransitionService,
    NotificationService,
    FakeUserRepository,
    User,
    User,
]:
    admin = make_user("01ADMIN", "admin@clinic.com", "Admin Base", UserRole.ADMIN)
    inactive_admin = make_user(
        "01INACT",
        "inactive.admin@clinic.com",
        "Inactive Admin",
        UserRole.ADMIN,
        is_active=False,
    )
    patient = make_user("01PATIENT", "user@clinic.com", "Paciente", UserRole.PATIENT)
    email_repo = FakeEmailNotificationRepository()
    user_repo = FakeUserRepository([admin, inactive_admin, patient])
    notification_service = NotificationService(email_repo)  # type: ignore[arg-type]
    transition_service = RoleTransitionService(
        repository=FakeRoleTransitionRepository(),  # type: ignore[arg-type]
        user_repository=user_repo,  # type: ignore[arg-type]
        notification_service=notification_service,
    )
    return transition_service, notification_service, user_repo, admin, patient


def test_request_and_approve_transition_updates_role_and_alerts_only_active_admins() -> None:  # noqa: E501
    service, notifications, _, admin, patient = build_fixture()

    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )
    assert request.status == TransitionStatus.PENDING.value

    approved = service.approve_transition(admin_user=admin, request_id=request.id)
    assert approved.status == TransitionStatus.APPROVED.value
    assert approved.reviewed_by_id == admin.id
    assert approved.reviewed_at is not None
    assert patient.role == UserRole.DOCTOR.value

    all_emails = notifications.list_emails(
        requester_email=admin.email,
        is_admin=True,
    )
    assert [(email.recipient_email, email.event_type) for email in all_emails] == [
        (patient.email, EmailEventType.ROLE_TRANSITION_REQUESTED.value),
        (admin.email, EmailEventType.ROLE_TRANSITION_ADMIN_ALERT.value),
        (patient.email, EmailEventType.ROLE_TRANSITION_APPROVED.value),
    ]


def test_reject_transition_keeps_role_and_allows_subsequent_new_request() -> None:
    service, notifications, _, admin, patient = build_fixture()

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

    second_request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )
    assert second_request.status == TransitionStatus.PENDING.value


def test_request_transition_blocks_duplicate_pending_same_role_and_admin() -> None:
    service, _, _, admin, patient = build_fixture()

    with pytest.raises(InvalidRoleTransitionError):
        service.request_transition(
            current_user=admin,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )

    service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    with pytest.raises(PendingRoleTransitionExistsError):
        service.request_transition(
            current_user=patient,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.ATTENDANT),
        )

    doctor = make_user("01DOC", "doc@clinic.com", "Dr. Ana", UserRole.DOCTOR)
    with pytest.raises(InvalidRoleTransitionError):
        service.request_transition(
            current_user=doctor,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )


def test_review_transition_validates_permissions_and_missing_entities() -> None:
    service, _, user_repo, admin, patient = build_fixture()

    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    with pytest.raises(RoleTransitionPermissionError):
        service.approve_transition(admin_user=patient, request_id=request.id)

    with pytest.raises(RoleTransitionNotFoundError):
        service.approve_transition(admin_user=admin, request_id="NONEXISTENT")

    del user_repo.users[patient.id]
    with pytest.raises(UserNotFoundError):
        service.approve_transition(admin_user=admin, request_id=request.id)


def test_list_requests_filters_by_status() -> None:
    service, _, _, admin, patient = build_fixture()
    other = make_user("01PAT2", "p2@clinic.com", "P2", UserRole.PATIENT)
    service.user_repository.users[other.id] = other  # type: ignore[attr-defined]

    req1 = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )
    req2 = service.request_transition(
        current_user=other,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.ATTENDANT),
    )
    service.approve_transition(admin_user=admin, request_id=req1.id)

    assert len(service.list_requests()) == 2
    assert [r.id for r in service.list_requests(status=TransitionStatus.PENDING)] == [
        req2.id
    ]
    assert [r.id for r in service.list_requests(status=TransitionStatus.APPROVED)] == [
        req1.id
    ]
