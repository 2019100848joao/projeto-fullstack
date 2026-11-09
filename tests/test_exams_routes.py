import os
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

os.environ["RUN_MIGRATIONS_ON_STARTUP"] = "false"

from app.main import app
from app.modules.auth.dependencies import get_current_user
from app.modules.auth.enums import UserRole
from app.modules.exams.dependencies import get_exam_service
from app.modules.exams.enums import ExamStatus
from app.modules.exams.models import Exam
from app.modules.users.models import User

NOW = datetime(2026, 10, 16, 11, 0, tzinfo=UTC)


def make_user(user_id: str, role: UserRole) -> User:
    return User(
        id=user_id,
        email=f"{user_id}@example.com",
        full_name=user_id,
        hashed_password="hashed",
        role=role.value,
        is_active=True,
        created_at=NOW,
    )


def make_exam() -> Exam:
    return Exam(
        id="exam",
        appointment_id="appointment",
        patient_id="patient",
        doctor_id="doctor",
        patient=make_user("patient", UserRole.PATIENT),
        doctor=make_user("doctor", UserRole.DOCTOR),
        name="Blood count",
        status=ExamStatus.RESULT_AVAILABLE.value,
        scheduled_at=NOW,
        performed_at=NOW,
        result="Confidential result",
        result_available_at=NOW,
        created_at=NOW,
    )


class FakeExamService:
    def list_exams(self, **kwargs: object) -> list[Exam]:
        return [make_exam()]

    def list_results(self, **kwargs: object) -> list[Exam]:
        return [make_exam()]

    def get_exam(self, **kwargs: object) -> Exam:
        return make_exam()

    def register_result(self, **kwargs: object) -> Exam:
        return make_exam()


def request_as(role: UserRole, method: str, path: str, body: object = None):
    app.dependency_overrides[get_current_user] = lambda: make_user("user", role)
    app.dependency_overrides[get_exam_service] = FakeExamService

    try:
        return TestClient(app).request(method, path, json=body)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("GET", "/exams", None),
        ("GET", "/exams/exam", None),
        ("POST", "/exams/exam/result", {"result": "Confidential result"}),
    ],
)
def test_exam_routes_do_not_return_the_result(
    method: str,
    path: str,
    body: object,
) -> None:
    response = request_as(UserRole.ATTENDANT, method, path, body)

    payload = response.json()
    exam = payload[0] if isinstance(payload, list) else payload

    assert response.status_code == 200
    assert "result" not in exam
    assert exam["status"] == "result_available"
    assert "Confidential result" not in response.text


@pytest.mark.parametrize("role", [UserRole.PATIENT, UserRole.DOCTOR, UserRole.ADMIN])
def test_results_route_returns_the_result(role: UserRole) -> None:
    response = request_as(role, "GET", "/exams/results")

    assert response.status_code == 200
    assert response.json()[0]["result"] == "Confidential result"


def test_blank_result_is_rejected() -> None:
    response = request_as(
        UserRole.ATTENDANT,
        "POST",
        "/exams/exam/result",
        {"result": "  "},
    )

    assert response.status_code == 422
