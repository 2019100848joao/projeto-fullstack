from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.database import Base
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import UserNotFoundError
from app.modules.notifications.enums import EmailEventType
from app.modules.notifications.models import EmailNotification
from app.modules.notifications.repository import EmailNotificationRepository
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
from app.modules.role_transitions.repository import RoleTransitionRepository
from app.modules.role_transitions.schemas import RoleTransitionCreate
from app.modules.role_transitions.service import RoleTransitionService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


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


class FakeUserRepository:
    def __init__(self, users: list[User]) -> None:
        self.users = {user.id: user for user in users}

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

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

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def create(
        self,
        *,
        user_id: str,
        requested_role: TransitionTargetRole,
    ) -> RoleTransitionRequest:
        if any(
            item.user_id == user_id and item.status == TransitionStatus.PENDING.value
            for item in self.requests.values()
        ):
            raise IntegrityError("INSERT", {}, Exception("unique pending"))
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

    def get_by_id(
        self,
        request_id: str,
        *,
        for_update: bool = False,
    ) -> RoleTransitionRequest | None:
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


def build_service() -> tuple[
    RoleTransitionService,
    NotificationService,
    FakeUserRepository,
    User,
    User,
]:
    admin = make_user("01ADMIN", "admin@clinic.com", "Admin Base", UserRole.ADMIN)
    inactive_admin = make_user(
        "01INACT",
        "inactive@clinic.com",
        "Inactive Admin",
        UserRole.ADMIN,
        is_active=False,
    )
    patient = make_user("01PATIENT", "user@clinic.com", "Paciente", UserRole.PATIENT)
    user_repository = FakeUserRepository([admin, inactive_admin, patient])
    notification_service = NotificationService(FakeEmailNotificationRepository())
    service = RoleTransitionService(
        repository=FakeRoleTransitionRepository(),
        user_repository=user_repository,
        notification_service=notification_service,
    )
    return service, notification_service, user_repository, admin, patient


def test_request_transition_creates_pending_and_notifies_active_admins() -> None:
    service, notifications, _, admin, patient = build_service()

    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    assert request.status == TransitionStatus.PENDING.value
    all_emails = notifications.list_emails(requester_email=admin.email, is_admin=True)
    assert [(email.recipient_email, email.event_type) for email in all_emails] == [
        (patient.email, EmailEventType.ROLE_TRANSITION_REQUESTED.value),
        (admin.email, EmailEventType.ROLE_TRANSITION_ADMIN_ALERT.value),
    ]


def test_approve_transition_updates_user_role_and_records_approval_email() -> None:
    service, notifications, _, admin, patient = build_service()
    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    approved = service.approve_transition(admin_user=admin, request_id=request.id)

    assert approved.status == TransitionStatus.APPROVED.value
    assert approved.reviewed_by_id == admin.id
    assert patient.role == UserRole.DOCTOR.value
    patient_emails = notifications.list_emails(
        requester_email=patient.email,
        is_admin=False,
    )
    assert (
        patient_emails[-1].event_type == EmailEventType.ROLE_TRANSITION_APPROVED.value
    )


def test_reject_transition_keeps_patient_role_and_records_rejection_email() -> None:
    service, notifications, _, admin, patient = build_service()
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
    assert (
        patient_emails[-1].event_type == EmailEventType.ROLE_TRANSITION_REJECTED.value
    )


def test_request_transition_rejects_duplicate_pending_request() -> None:
    service, _, _, _, patient = build_service()
    service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    with pytest.raises(PendingRoleTransitionExistsError):
        service.request_transition(
            current_user=patient,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.ATTENDANT),
        )


def test_request_transition_allows_new_request_after_rejection() -> None:
    service, _, _, admin, patient = build_service()
    first = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.ATTENDANT),
    )
    service.reject_transition(admin_user=admin, request_id=first.id)

    second = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    assert second.status == TransitionStatus.PENDING.value


def test_request_transition_rejects_admin_and_same_role() -> None:
    service, _, _, admin, _ = build_service()
    doctor = make_user("01DOC", "doc@clinic.com", "Dr. Ana", UserRole.DOCTOR)

    with pytest.raises(InvalidRoleTransitionError):
        service.request_transition(
            current_user=admin,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )

    with pytest.raises(InvalidRoleTransitionError):
        service.request_transition(
            current_user=doctor,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )


def test_review_transition_rejects_non_admin_and_already_reviewed() -> None:
    service, _, _, admin, patient = build_service()
    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    with pytest.raises(RoleTransitionPermissionError):
        service.approve_transition(admin_user=patient, request_id=request.id)

    service.approve_transition(admin_user=admin, request_id=request.id)

    with pytest.raises(RoleTransitionAlreadyReviewedError):
        service.reject_transition(admin_user=admin, request_id=request.id)


def test_review_transition_raises_when_request_or_user_is_missing() -> None:
    service, _, user_repository, admin, patient = build_service()
    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )

    with pytest.raises(RoleTransitionNotFoundError):
        service.approve_transition(admin_user=admin, request_id="NONEXISTENT")

    del user_repository.users[patient.id]
    with pytest.raises(UserNotFoundError):
        service.approve_transition(admin_user=admin, request_id=request.id)


def test_role_transition_workflow_persists_in_database() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user_repository = UserRepository(db)
        email_repository = EmailNotificationRepository(db)
        transition_repository = RoleTransitionRepository(db)
        notification_service = NotificationService(email_repository)
        service = RoleTransitionService(
            repository=transition_repository,
            user_repository=user_repository,
            notification_service=notification_service,
        )

        admin = user_repository.create(
            email="admin@clinic.com",
            full_name="Clinic Administrator",
            hashed_password="hashed-password",
            role=UserRole.ADMIN,
        )
        patient = user_repository.create(
            email="patient@example.com",
            full_name="Patient Example",
            hashed_password="hashed-password",
            role=UserRole.PATIENT,
        )

        created = service.request_transition(
            current_user=patient,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )
        assert len(service.list_requests(status=TransitionStatus.PENDING)) == 1

        approved = service.approve_transition(
            admin_user=admin,
            request_id=created.id,
        )
        assert approved.status == "approved"
        updated_patient = user_repository.get_by_id(patient.id)
        assert updated_patient is not None
        assert updated_patient.role == "doctor"
        assert len(email_repository.list_all()) == 3


class FailingEmailNotificationRepository(FakeEmailNotificationRepository):
    def create(self, **kwargs: object) -> EmailNotification:
        raise RuntimeError("email storage unavailable")


def build_db_service(
    db: Session,
    notification_service: NotificationService | None = None,
) -> tuple[RoleTransitionService, UserRepository, User, User]:
    user_repository = UserRepository(db)
    service = RoleTransitionService(
        repository=RoleTransitionRepository(db),
        user_repository=user_repository,
        notification_service=notification_service
        or NotificationService(EmailNotificationRepository(db)),
    )
    admin = user_repository.create(
        email="admin@clinic.com",
        full_name="Clinic Administrator",
        hashed_password="hashed-password",
        role=UserRole.ADMIN,
    )
    patient = user_repository.create(
        email="patient@example.com",
        full_name="Patient Example",
        hashed_password="hashed-password",
        role=UserRole.PATIENT,
    )
    db.commit()
    return service, user_repository, admin, patient


def make_engine():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_unique_index_blocks_second_pending_request_in_database() -> None:
    with Session(make_engine()) as db:
        service, _, _, patient = build_db_service(db)
        service.request_transition(
            current_user=patient,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )

        with pytest.raises(PendingRoleTransitionExistsError):
            service.request_transition(
                current_user=patient,
                payload=RoleTransitionCreate(
                    requested_role=TransitionTargetRole.ATTENDANT
                ),
            )

        assert len(service.list_requests(status=TransitionStatus.PENDING)) == 1


def test_approve_rejects_request_when_user_role_changed_meanwhile() -> None:
    service, _, user_repository, admin, patient = build_service()
    request = service.request_transition(
        current_user=patient,
        payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
    )
    user_repository.update_role(patient, UserRole.ADMIN)

    with pytest.raises(InvalidRoleTransitionError):
        service.approve_transition(admin_user=admin, request_id=request.id)

    assert patient.role == UserRole.ADMIN.value
    assert request.status == TransitionStatus.PENDING.value


def test_approve_is_atomic_when_notification_fails() -> None:
    engine = make_engine()
    with Session(engine) as db:
        service, _, admin, patient = build_db_service(db)
        request = service.request_transition(
            current_user=patient,
            payload=RoleTransitionCreate(requested_role=TransitionTargetRole.DOCTOR),
        )
        request_id, patient_id, admin_id = request.id, patient.id, admin.id

    with Session(engine) as db:
        failing_service = RoleTransitionService(
            repository=RoleTransitionRepository(db),
            user_repository=UserRepository(db),
            notification_service=NotificationService(
                FailingEmailNotificationRepository()
            ),
        )
        admin = UserRepository(db).get_by_id(admin_id)
        assert admin is not None
        with pytest.raises(RuntimeError):
            failing_service.approve_transition(admin_user=admin, request_id=request_id)

    with Session(engine) as db:
        stored_patient = UserRepository(db).get_by_id(patient_id)
        stored_request = RoleTransitionRepository(db).get_by_id(request_id)
        assert stored_patient is not None and stored_request is not None
        assert stored_patient.role == UserRole.PATIENT.value
        assert stored_request.status == TransitionStatus.PENDING.value
