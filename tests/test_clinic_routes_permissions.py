import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User

APPOINTMENT_BODY = {
    "patient_id": "patient",
    "doctor_id": "doctor",
    "scheduled_at": "2026-10-14T10:00:00-03:00",
}
EXAM_SCHEDULE_BODY = {"scheduled_at": "2026-10-16T08:00:00-03:00"}


def request_as(
    role: UserRole | None,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> int:
    def override_current_user() -> User:
        return User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email="user@example.com",
            full_name="Example",
            hashed_password="not-returned",
            role=role.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )

    if role is not None:
        app.dependency_overrides[get_current_user] = override_current_user

    try:
        response = TestClient(app).request(method, path, json=body)
    finally:
        app.dependency_overrides.clear()

    return response.status_code


@pytest.mark.parametrize(
    ("role", "method", "path", "body"),
    [
        (UserRole.PATIENT, "POST", "/appointments", APPOINTMENT_BODY),
        (UserRole.DOCTOR, "POST", "/appointments", APPOINTMENT_BODY),
        (UserRole.DOCTOR, "GET", "/appointments", None),
        (UserRole.DOCTOR, "POST", "/appointments/id/cancel", None),
        (UserRole.ATTENDANT, "GET", "/appointments/agenda", None),
        (UserRole.PATIENT, "GET", "/appointments/agenda", None),
        (UserRole.ATTENDANT, "POST", "/appointments/id/attendance", {}),
        (UserRole.PATIENT, "GET", "/appointments/id", None),
        (UserRole.DOCTOR, "POST", "/exams/id/schedule", EXAM_SCHEDULE_BODY),
        (UserRole.PATIENT, "POST", "/exams/id/perform", None),
        (UserRole.DOCTOR, "POST", "/exams/id/result", {"result": "Normal"}),
    ],
)
def test_role_without_permission_is_forbidden(
    role: UserRole,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    assert request_as(role, method, path, body) == 403


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/appointments/agenda"),
        ("GET", "/exams"),
    ],
)
def test_clinic_routes_require_authentication(method: str, path: str) -> None:
    assert request_as(None, method, path, None) == 401
