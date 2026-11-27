from datetime import UTC, datetime

import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.core import seed
from app.core.config import Settings
from app.core.security import decode_access_token, hash_password
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
    def __init__(self, user: User | None = None) -> None:
        self.user = user
        self.created_role: UserRole | None = None
        self.create_calls = 0

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

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


def test_register_creates_patient_and_records_welcome_email() -> None:
    repository = FakeUserRepository()
    email_repository = FakeEmailNotificationRepository()
    notifications = NotificationService(email_repository)
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
    assert len(email_repository.items) == 1
    assert email_repository.items[0].event_type == EmailEventType.USER_REGISTERED.value


@pytest.mark.parametrize("disallowed_role", ["doctor", "attendant", "admin"])
def test_user_create_rejects_privileged_roles(disallowed_role: str) -> None:
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                "email": "user@example.com",
                "full_name": "User Example",
                "password": "password123",
                "role": disallowed_role,
            }
        )


def test_ensure_base_admin_creates_admin_once() -> None:
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
        password="Admin123!",
    )

    assert repository.create_calls == 1
    assert repository.created_role == UserRole.ADMIN
    assert first.role == "admin"
    assert second.id == first.id


def test_login_returns_valid_access_token() -> None:
    user = make_user(UserRole.PATIENT)
    service = AuthService(FakeUserRepository(user))

    token = service.login(email=user.email, password="password123")

    payload = decode_access_token(token.access_token)
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
    service = AuthService(FakeUserRepository(make_user(UserRole.PATIENT)))

    assert len(service.list_users(role=UserRole.PATIENT)) == 1
    assert service.list_users(role=UserRole.DOCTOR) == []


def test_admin_can_change_any_user_role() -> None:
    service = AuthService(FakeUserRepository(make_user(UserRole.PATIENT)))

    updated_user = service.update_user_role(
        current_user=make_user(UserRole.ADMIN),
        target_user_id="01K4SRY37DGE7K5YWWKNB0RESW",
        new_role=UserRole.DOCTOR,
    )

    assert updated_user.role == "doctor"


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
def test_role_change_rejects_disallowed_change(
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


class RacingUserRepository(FakeUserRepository):
    """Simulates another worker inserting the same email between check and insert."""

    def __init__(self, winner: User) -> None:
        super().__init__()
        self.winner = winner
        self.rolled_back = False

    def create(self, **kwargs: object) -> User:
        self.user = self.winner
        raise IntegrityError("INSERT", {}, Exception("duplicate email"))

    def rollback(self) -> None:
        self.rolled_back = True


def test_ensure_base_admin_returns_existing_admin_on_concurrent_insert() -> None:
    winner = make_user(UserRole.ADMIN)
    repository = RacingUserRepository(winner)
    service = AuthService(repository)

    admin = service.ensure_base_admin(
        email=winner.email,
        full_name="Clinic Administrator",
        password="Admin123!",
    )

    assert admin is winner
    assert repository.rolled_back


def test_register_maps_concurrent_duplicate_email_to_domain_error() -> None:
    winner = make_user(UserRole.PATIENT)
    repository = RacingUserRepository(winner)
    service = AuthService(repository)

    with pytest.raises(EmailAlreadyRegisteredError):
        service.register(
            UserCreate(
                email=winner.email,
                full_name="Dr. Example",
                password="password123",
            )
        )
    assert repository.rolled_back


def test_seed_admin_defaults_apply_only_in_local_environment() -> None:
    local = Settings(_env_file=None, app_env="development")
    production = Settings(_env_file=None, app_env="production")
    explicit = Settings(
        _env_file=None,
        app_env="production",
        seed_admin_email="root@clinic.com",
        seed_admin_password="S3cure-pass",
    )

    assert (local.seed_admin_email, local.seed_admin_password) == (
        "admin@clinic.com",
        "Admin123!",
    )
    assert production.seed_admin_email is None
    assert production.seed_admin_password is None
    assert explicit.seed_admin_email == "root@clinic.com"


def test_seed_is_skipped_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(seed.settings, "seed_admin_email", None)
    monkeypatch.setattr(seed.settings, "seed_admin_password", None)

    assert seed.ensure_base_admin(db=None) is None  # type: ignore[arg-type]
