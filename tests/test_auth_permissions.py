from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import require_roles
from app.modules.auth.enums import UserRole
from app.modules.auth.models import User
from app.modules.auth.permissions import PermissionService


def make_user(role: UserRole) -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="doctor@example.com",
        full_name="Dr. Example",
        hashed_password="not-returned",
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )


def test_permission_service_allows_matching_role() -> None:
    service = PermissionService()
    user = make_user(UserRole.DOCTOR)

    assert service.user_has_any_role(user, {UserRole.ADMIN, UserRole.DOCTOR})


def test_permission_service_rejects_non_matching_role() -> None:
    service = PermissionService()
    user = make_user(UserRole.PATIENT)

    assert not service.user_has_any_role(user, {UserRole.ADMIN})


def test_permission_service_allows_appointment_creators() -> None:
    service = PermissionService()

    assert service.can_create_appointment(make_user(UserRole.DOCTOR))
    assert service.can_create_appointment(make_user(UserRole.ATTENDANT))
    assert not service.can_create_appointment(make_user(UserRole.PATIENT))


def test_permission_service_checks_role_change_rules() -> None:
    service = PermissionService()

    assert service.can_change_user_role(
        current_user=make_user(UserRole.ADMIN),
        target_user=make_user(UserRole.PATIENT),
        new_role=UserRole.DOCTOR,
    )
    assert service.can_change_user_role(
        current_user=make_user(UserRole.ATTENDANT),
        target_user=make_user(UserRole.PATIENT),
        new_role=UserRole.ATTENDANT,
    )
    assert not service.can_change_user_role(
        current_user=make_user(UserRole.DOCTOR),
        target_user=make_user(UserRole.PATIENT),
        new_role=UserRole.ADMIN,
    )


def test_require_roles_rejects_non_matching_role_with_http_error() -> None:
    permission = require_roles(UserRole.ADMIN)
    user = make_user(UserRole.PATIENT)

    with pytest.raises(HTTPException) as exc_info:
        permission(user)

    assert exc_info.value.status_code == 403
