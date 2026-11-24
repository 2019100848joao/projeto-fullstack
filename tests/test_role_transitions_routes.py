import os
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.core.database import Base, get_db
from app.core.seed import ensure_base_admin
from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.role_transitions.dependencies import get_role_transition_service
from app.modules.role_transitions.enums import TransitionStatus
from app.modules.role_transitions.exceptions import (
    InvalidRoleTransitionError,
    PendingRoleTransitionExistsError,
    RoleTransitionAlreadyReviewedError,
    RoleTransitionNotFoundError,
)
from app.modules.role_transitions.models import RoleTransitionRequest
from app.modules.role_transitions.schemas import RoleTransitionCreate

REQUEST_ID = "01K4SRY37DGE7K5YWWKNB0REQ1"
USER_ID = "01K4SRY37DGE7K5YWWKNB0RESW"
ADMIN_ID = "01K4SRY37DGE7K5YWWKNB0ADM1"


def make_user(role: UserRole, user_id: str = USER_ID) -> User:
    return User(
        id=user_id,
        email="user@example.com",
        full_name="Example User",
        hashed_password="not-returned",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


class FakeRoleTransitionService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.status_filter: TransitionStatus | None = None

    def request_transition(
        self,
        *,
        current_user: User,
        payload: RoleTransitionCreate,
    ) -> RoleTransitionRequest:
        if self.error is not None:
            raise self.error
        return RoleTransitionRequest(
            id=REQUEST_ID,
            user_id=current_user.id,
            requested_role=payload.requested_role.value,
            status=TransitionStatus.PENDING.value,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    def list_requests(
        self,
        *,
        status: TransitionStatus | None = None,
    ) -> list[RoleTransitionRequest]:
        self.status_filter = status
        return [
            RoleTransitionRequest(
                id=REQUEST_ID,
                user_id=USER_ID,
                requested_role="doctor",
                status=(status or TransitionStatus.PENDING).value,
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        ]

    def approve_transition(
        self,
        *,
        admin_user: User,
        request_id: str,
    ) -> RoleTransitionRequest:
        if self.error is not None:
            raise self.error
        return RoleTransitionRequest(
            id=request_id,
            user_id=USER_ID,
            requested_role="doctor",
            status=TransitionStatus.APPROVED.value,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
            reviewed_by_id=admin_user.id,
            reviewed_at=datetime(2026, 9, 10, tzinfo=UTC),
        )

    def reject_transition(
        self,
        *,
        admin_user: User,
        request_id: str,
    ) -> RoleTransitionRequest:
        if self.error is not None:
            raise self.error
        return RoleTransitionRequest(
            id=request_id,
            user_id=USER_ID,
            requested_role="attendant",
            status=TransitionStatus.REJECTED.value,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
            reviewed_by_id=admin_user.id,
            reviewed_at=datetime(2026, 9, 10, tzinfo=UTC),
        )


def override_role_transition_service() -> FakeRoleTransitionService:
    return FakeRoleTransitionService()


def test_request_role_transition_returns_201() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.PATIENT)
    app.dependency_overrides[get_role_transition_service] = (
        override_role_transition_service
    )

    try:
        response = TestClient(app).post(
            "/role-transitions",
            json={"requested_role": "doctor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["status"] == "pending"


@pytest.mark.parametrize("invalid_role", ["admin", "patient"])
def test_request_role_transition_rejects_disallowed_target_role(
    invalid_role: str,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.PATIENT)
    app.dependency_overrides[get_role_transition_service] = (
        override_role_transition_service
    )

    try:
        response = TestClient(app).post(
            "/role-transitions",
            json={"requested_role": invalid_role},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


def test_request_role_transition_returns_400_when_invalid() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.DOCTOR)
    app.dependency_overrides[get_role_transition_service] = lambda: (
        FakeRoleTransitionService(error=InvalidRoleTransitionError())
    )

    try:
        response = TestClient(app).post(
            "/role-transitions",
            json={"requested_role": "doctor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400


def test_request_role_transition_returns_409_when_pending_exists() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(UserRole.PATIENT)
    app.dependency_overrides[get_role_transition_service] = lambda: (
        FakeRoleTransitionService(error=PendingRoleTransitionExistsError())
    )

    try:
        response = TestClient(app).post(
            "/role-transitions",
            json={"requested_role": "doctor"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/role-transitions", {"requested_role": "doctor"}),
        ("GET", "/role-transitions", None),
        ("POST", f"/role-transitions/{REQUEST_ID}/approve", None),
        ("POST", f"/role-transitions/{REQUEST_ID}/reject", None),
    ],
)
def test_role_transition_routes_require_authentication(
    method: str,
    path: str,
    body: dict[str, str] | None,
) -> None:
    response = TestClient(app).request(method, path, json=body)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.PATIENT, UserRole.DOCTOR, UserRole.ATTENDANT],
)
@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/role-transitions"),
        ("POST", f"/role-transitions/{REQUEST_ID}/approve"),
        ("POST", f"/role-transitions/{REQUEST_ID}/reject"),
    ],
)
def test_admin_only_role_transition_routes_forbid_non_admins(
    role: UserRole,
    method: str,
    path: str,
) -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(role)
    app.dependency_overrides[get_role_transition_service] = (
        override_role_transition_service
    )

    try:
        response = TestClient(app).request(method, path)
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_admin_can_list_role_transitions_by_status() -> None:
    service = FakeRoleTransitionService()
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.ADMIN, ADMIN_ID
    )
    app.dependency_overrides[get_role_transition_service] = lambda: service

    try:
        response = TestClient(app).get("/role-transitions?status=pending")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.status_filter == TransitionStatus.PENDING


def test_admin_can_approve_role_transition() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.ADMIN, ADMIN_ID
    )
    app.dependency_overrides[get_role_transition_service] = (
        override_role_transition_service
    )

    try:
        response = TestClient(app).post(f"/role-transitions/{REQUEST_ID}/approve")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "approved"


def test_admin_can_reject_role_transition() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.ADMIN, ADMIN_ID
    )
    app.dependency_overrides[get_role_transition_service] = (
        override_role_transition_service
    )

    try:
        response = TestClient(app).post(f"/role-transitions/{REQUEST_ID}/reject")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_review_role_transition_returns_404_when_not_found() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.ADMIN, ADMIN_ID
    )
    app.dependency_overrides[get_role_transition_service] = lambda: (
        FakeRoleTransitionService(error=RoleTransitionNotFoundError())
    )

    try:
        response = TestClient(app).post(f"/role-transitions/{REQUEST_ID}/approve")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


def test_review_role_transition_returns_409_when_already_reviewed() -> None:
    app.dependency_overrides[get_current_user] = lambda: make_user(
        UserRole.ADMIN, ADMIN_ID
    )
    app.dependency_overrides[get_role_transition_service] = lambda: (
        FakeRoleTransitionService(error=RoleTransitionAlreadyReviewedError())
    )

    try:
        response = TestClient(app).post(f"/role-transitions/{REQUEST_ID}/approve")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409


def test_end_to_end_transition_flow_updates_role_and_records_emails() -> None:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db() -> Generator[Session]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    with session_factory() as db:
        ensure_base_admin(db)

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app)
        client.post(
            "/auth/register",
            json={
                "email": "maria@example.com",
                "full_name": "Maria Silva",
                "password": "password123",
            },
        )
        patient_token = client.post(
            "/auth/login",
            json={"email": "maria@example.com", "password": "password123"},
        ).json()["access_token"]
        admin_token = client.post(
            "/auth/login",
            json={"email": "admin@clinic.com", "password": "Admin123!"},
        ).json()["access_token"]

        created = client.post(
            "/role-transitions",
            headers={"Authorization": f"Bearer {patient_token}"},
            json={"requested_role": "doctor"},
        ).json()
        client.post(
            f"/role-transitions/{created['id']}/approve",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        me = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {patient_token}"},
        ).json()
        emails = client.get(
            "/notifications/emails",
            headers={"Authorization": f"Bearer {admin_token}"},
        ).json()
    finally:
        app.dependency_overrides.clear()

    assert me["role"] == "doctor"
    assert {item["event_type"] for item in emails} == {
        "user_registered",
        "role_transition_requested",
        "role_transition_admin_alert",
        "role_transition_approved",
    }
