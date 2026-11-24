import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

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
    RoleTransitionPermissionError,
)
from app.modules.role_transitions.models import RoleTransitionRequest
from app.modules.role_transitions.schemas import RoleTransitionCreate

REQ_ID = "01K4SRY37DGE7K5YWWKNB0REQ1"
USER_ID = "01K4SRY37DGE7K5YWWKNB0RESW"
ADMIN_ID = "01K4SRY37DGE7K5YWWKNB0ADM1"


def _make_user(role: UserRole, user_id: str = USER_ID) -> User:
    return User(
        id=user_id,
        email=f"{role.value}@clinic.com",
        full_name=f"User {role.value}",
        hashed_password="hashed-password",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


class StubRoleTransitionService:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.last_status_filter: TransitionStatus | None = None

    def request_transition(
        self,
        *,
        current_user: User,
        payload: RoleTransitionCreate,
    ) -> RoleTransitionRequest:
        if self.error is not None:
            raise self.error
        return RoleTransitionRequest(
            id=REQ_ID,
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
        self.last_status_filter = status
        return [
            RoleTransitionRequest(
                id=REQ_ID,
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


def test_request_role_transition_route_status_codes() -> None:
    client = TestClient(app)
    assert (
        client.post("/role-transitions", json={"requested_role": "doctor"}).status_code
        == 401
    )

    app.dependency_overrides[get_current_user] = lambda: _make_user(UserRole.PATIENT)
    try:
        app.dependency_overrides[get_role_transition_service] = lambda: (
            StubRoleTransitionService()
        )
        ok = client.post("/role-transitions", json={"requested_role": "doctor"})
        assert ok.status_code == 201
        assert ok.json()["status"] == "pending"

        for bad_target in ("admin", "patient"):
            bad = client.post("/role-transitions", json={"requested_role": bad_target})
            assert bad.status_code == 422

        extra = client.post(
            "/role-transitions",
            json={"requested_role": "doctor", "unexpected": "field"},
        )
        assert extra.status_code == 422

        app.dependency_overrides[get_role_transition_service] = lambda: (
            StubRoleTransitionService(error=InvalidRoleTransitionError())
        )
        assert (
            client.post(
                "/role-transitions", json={"requested_role": "doctor"}
            ).status_code
            == 400
        )

        app.dependency_overrides[get_role_transition_service] = lambda: (
            StubRoleTransitionService(error=PendingRoleTransitionExistsError())
        )
        assert (
            client.post(
                "/role-transitions", json={"requested_role": "doctor"}
            ).status_code
            == 409
        )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "non_admin_role",
    [UserRole.PATIENT, UserRole.DOCTOR, UserRole.ATTENDANT],
)
def test_admin_only_role_transition_endpoints_reject_non_admins(
    non_admin_role: UserRole,
) -> None:
    client = TestClient(app)
    assert client.get("/role-transitions").status_code == 401
    assert client.post(f"/role-transitions/{REQ_ID}/approve").status_code == 401
    assert client.post(f"/role-transitions/{REQ_ID}/reject").status_code == 401

    app.dependency_overrides[get_current_user] = lambda: _make_user(non_admin_role)
    app.dependency_overrides[get_role_transition_service] = lambda: (
        StubRoleTransitionService()
    )
    try:
        assert client.get("/role-transitions").status_code == 403
        assert client.post(f"/role-transitions/{REQ_ID}/approve").status_code == 403
        assert client.post(f"/role-transitions/{REQ_ID}/reject").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_list_approve_and_reject_routes_for_admin() -> None:
    stub = StubRoleTransitionService()
    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: _make_user(
        UserRole.ADMIN, ADMIN_ID
    )
    app.dependency_overrides[get_role_transition_service] = lambda: stub
    try:
        listed = client.get("/role-transitions", params={"status": "pending"})
        assert listed.status_code == 200
        assert stub.last_status_filter == TransitionStatus.PENDING
        assert listed.json()[0]["status"] == "pending"

        approved = client.post(f"/role-transitions/{REQ_ID}/approve")
        assert approved.status_code == 200
        assert approved.json()["status"] == "approved"
        assert approved.json()["reviewed_by_id"] == ADMIN_ID

        rejected = client.post(f"/role-transitions/{REQ_ID}/reject")
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "rejected"

        app.dependency_overrides[get_role_transition_service] = lambda: (
            StubRoleTransitionService(error=RoleTransitionNotFoundError())
        )
        assert client.post(f"/role-transitions/{REQ_ID}/approve").status_code == 404
        assert client.post(f"/role-transitions/{REQ_ID}/reject").status_code == 404

        app.dependency_overrides[get_role_transition_service] = lambda: (
            StubRoleTransitionService(error=RoleTransitionAlreadyReviewedError())
        )
        assert client.post(f"/role-transitions/{REQ_ID}/approve").status_code == 409
        assert client.post(f"/role-transitions/{REQ_ID}/reject").status_code == 409

        app.dependency_overrides[get_role_transition_service] = lambda: (
            StubRoleTransitionService(error=RoleTransitionPermissionError())
        )
        assert client.post(f"/role-transitions/{REQ_ID}/approve").status_code == 403
    finally:
        app.dependency_overrides.clear()
