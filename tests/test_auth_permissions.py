from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.modules.auth.dependencies import require_roles
from app.modules.auth.enums import UserRole
from app.modules.users.models import User


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


def test_require_roles_allows_matching_role() -> None:
    permission = require_roles(UserRole.ADMIN, UserRole.DOCTOR)
    user = make_user(UserRole.DOCTOR)

    assert permission(user) is user


def test_require_roles_rejects_non_matching_role() -> None:
    permission = require_roles(UserRole.ADMIN)
    user = make_user(UserRole.PATIENT)

    with pytest.raises(HTTPException) as exc_info:
        permission(user)

    assert exc_info.value.status_code == 403
