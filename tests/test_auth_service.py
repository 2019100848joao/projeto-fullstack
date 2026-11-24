from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.security import decode_access_token, hash_password
from app.main import app, lifespan
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.models import User
from app.modules.auth.schemas import RegistrationRole, UserCreate
from app.modules.auth.service import AuthService
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


class FakeUserRepository:
    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.created_role: UserRole | None = None
        self.create_calls = 0

    def get_by_email(self, email: str) -> User | None:
        if self.user is not None and self.user.email == email:
            return self.user
        return None

    def get_by_id(self, user_id: str) -> User | None:
        return self.user

    def list_all(self, *, role: UserRole | None = None) -> list[User]:
        if self.user is None:
            return []
        if role is not None and self.user.role != role.value:
            return []
        return [self.user]

    def update_role(self, user: User, role: UserRole) -> User:
        user.role = role.value
        return user

    def create(
        self,
        *,
        email: str,
        full_name: str,
        hashed_password: str,
        role: UserRole = UserRole.PATIENT,
    ) -> User:
        self.create_calls += 1
        self.created_role = role
        self.user = User(
            id="01K4SRY37DGE7K5YWWKNB0RESW",
            email=email,
            full_name=full_name,
            hashed_password=hashed_password,
            role=role.value,
            is_active=True,
            created_at=datetime(2026, 9, 9, tzinfo=UTC),
        )
        return self.user


def test_register_raises_domain_error_when_email_exists() -> None:
    service = AuthService(
        FakeUserRepository(
            User(
                id="01K4SRY37DGE7K5YWWKNB0RESW",
                email="doctor@example.com",
                full_name="Dr. Example",
                hashed_password="hashed",
                role="doctor",
                is_active=True,
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register(
            UserCreate(
                email="doctor@example.com",
                full_name="Dr. Example",
                password="password123",
            )
        )


def test_register_creates_patient_only_and_records_welcome_email() -> None:
    repository = FakeUserRepository()
    email_repo = FakeEmailRepo()
    notifications = NotificationService(email_repo)  # type: ignore[arg-type]
    service = AuthService(repository, notification_service=notifications)

    user = service.register(
        UserCreate(
            email="patient@example.com",
            full_name="Patient Example",
            password="password123",
            role=RegistrationRole.PATIENT,
        )
    )

    assert repository.created_role == UserRole.PATIENT
    assert user.role == "patient"
    assert len(email_repo.items) == 1
    assert email_repo.items[0].recipient_email == "patient@example.com"
    assert email_repo.items[0].event_type == EmailEventType.USER_REGISTERED.value


@pytest.mark.parametrize("disallowed_role", ["doctor", "attendant", "admin"])
def test_user_create_schema_rejects_privileged_roles(disallowed_role: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate(
            email="user@example.com",
            full_name="User Example",
            password="password123",
            role=disallowed_role,  # type: ignore[arg-type]
        )


def test_ensure_base_admin_is_idempotent() -> None:
    repository = FakeUserRepository()
    service = AuthService(repository)

    first = service.ensure_base_admin(
        email="admin@clinic.com",
        full_name="Clinic Administrator",
        password="Admin123!",
    )
    second = service.ensure_base_admin(
        email="admin@clinic.com",
        full_name="Clinic Administrator",
        password="DifferentPassword!",
    )

    assert repository.create_calls == 1
    assert repository.created_role == UserRole.ADMIN
    assert first.role == "admin"
    assert second.id == first.id


def test_login_returns_valid_jwt_token() -> None:
    user = make_user(UserRole.PATIENT)
    service = AuthService(FakeUserRepository(user))

    token = service.login(email=user.email, password="password123")

    payload = decode_access_token(token.access_token)
    assert token.token_type == "bearer"
    assert payload["sub"] == user.id


def test_login_raises_domain_error_when_credentials_are_invalid() -> None:
    service = AuthService(FakeUserRepository())

    with pytest.raises(InvalidCredentialsError):
        service.login(email="doctor@example.com", password="wrong-password")


def test_login_raises_domain_error_when_user_is_inactive() -> None:
    service = AuthService(
        FakeUserRepository(
            User(
                id="01K4SRY37DGE7K5YWWKNB0RESW",
                email="doctor@example.com",
                full_name="Dr. Example",
                hashed_password=hash_password("password123"),
                role="doctor",
                is_active=False,
                created_at=datetime(2026, 9, 9, tzinfo=UTC),
            )
        )
    )

    with pytest.raises(InactiveUserError):
        service.login(email="doctor@example.com", password="password123")


def test_list_users_filters_by_role() -> None:
    patient = make_user(UserRole.PATIENT)
    service = AuthService(FakeUserRepository(patient))

    assert len(service.list_users()) == 1
    assert len(service.list_users(role=UserRole.PATIENT)) == 1
    assert service.list_users(role=UserRole.DOCTOR) == []


@pytest.mark.parametrize(
    ("target_initial_role", "new_role"),
    [
        (UserRole.PATIENT, UserRole.DOCTOR),
        (UserRole.PATIENT, UserRole.ATTENDANT),
        (UserRole.PATIENT, UserRole.ADMIN),
        (UserRole.DOCTOR, UserRole.PATIENT),
        (UserRole.ATTENDANT, UserRole.DOCTOR),
    ],
)
def test_admin_can_change_any_user_role(
    target_initial_role: UserRole,
    new_role: UserRole,
) -> None:
    service = AuthService(FakeUserRepository(make_user(target_initial_role)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.ADMIN),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=new_role,
    )

    assert updated_user.role == new_role.value


def test_doctor_can_change_attendant_to_patient() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.ATTENDANT)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.DOCTOR),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=UserRole.PATIENT,
    )

    assert updated_user.role == "patient"


def test_attendant_can_change_patient_to_attendant() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.PATIENT)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.ATTENDANT),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=UserRole.ATTENDANT,
    )

    assert updated_user.role == "attendant"


@pytest.mark.parametrize(
    ("actor_role", "target_role", "new_role"),
    [
        (UserRole.PATIENT, UserRole.PATIENT, UserRole.DOCTOR),
        (UserRole.DOCTOR, UserRole.PATIENT, UserRole.DOCTOR),
        (UserRole.DOCTOR, UserRole.ATTENDANT, UserRole.ADMIN),
        (UserRole.ATTENDANT, UserRole.PATIENT, UserRole.DOCTOR),
        (UserRole.ATTENDANT, UserRole.DOCTOR, UserRole.PATIENT),
    ],
)
def test_role_change_rejects_disallowed_combinations(
    actor_role: UserRole,
    target_role: UserRole,
    new_role: UserRole,
) -> None:
    service = AuthService(FakeUserRepository(make_user(target_role)))

    with pytest.raises(RoleChangeNotAllowedError):
        service.update_user_role(
            current_user=make_user(actor_role),
            target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
            new_role=new_role,
        )


def test_role_change_raises_when_user_does_not_exist() -> None:
    service = AuthService(FakeUserRepository())

    with pytest.raises(UserNotFoundError):
        service.update_user_role(
            current_user=make_user(UserRole.ADMIN),
            target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
            new_role=UserRole.DOCTOR,
        )


def test_lifespan_runs_migrations_and_seed_only_when_enabled() -> None:
    def drive_lifespan(migrations: bool, seed: bool) -> tuple[MagicMock, MagicMock]:
        with (
            patch("app.main.settings.run_migrations_on_startup", migrations),
            patch("app.main.settings.seed_admin_on_startup", seed),
            patch("app.main.run_migrations") as mock_migrations,
            patch("app.main.bootstrap_base_admin") as mock_seed,
        ):
            cm = lifespan(app)
            enter = cm.__aenter__()
            try:
                enter.send(None)
            except StopIteration:
                pass
            exit_coro = cm.__aexit__(None, None, None)
            try:
                exit_coro.send(None)
            except StopIteration:
                pass
            return mock_migrations, mock_seed

    mig_off, seed_off = drive_lifespan(False, True)
    assert mig_off.call_count == 0
    assert seed_off.call_count == 0

    mig_on, seed_disabled = drive_lifespan(True, False)
    assert mig_on.call_count == 1
    assert seed_disabled.call_count == 0

    mig_both, seed_both = drive_lifespan(True, True)
    assert mig_both.call_count == 1
    assert seed_both.call_count == 1


def make_user(role: UserRole) -> User:
    return User(
        id="01K4SRY37DGE7K5YWWKNB0RESW",
        email="doctor@example.com",
        full_name="Dr. Example",
        hashed_password=hash_password("password123"),
        role=role.value,
        is_active=True,
        created_at=datetime(2026, 9, 9, tzinfo=UTC),
    )
