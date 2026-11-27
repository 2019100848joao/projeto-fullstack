from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.schemas import Token, UserCreate
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository

ROLE_CHANGE_RULES: dict[UserRole, dict[UserRole, set[UserRole]]] = {
    UserRole.ADMIN: {
        UserRole.ADMIN: set(UserRole),
        UserRole.PATIENT: set(UserRole),
        UserRole.DOCTOR: set(UserRole),
        UserRole.ATTENDANT: set(UserRole),
    },
    UserRole.DOCTOR: {
        UserRole.ATTENDANT: {UserRole.PATIENT, UserRole.ATTENDANT},
    },
    UserRole.ATTENDANT: {
        UserRole.PATIENT: {UserRole.PATIENT, UserRole.ATTENDANT},
    },
}


class AuthService:
    def __init__(
        self,
        repository: UserRepository,
        notification_service: NotificationService | None = None,
    ) -> None:
        self.repository = repository
        self.notification_service = notification_service

    def register(self, user_create: UserCreate) -> User:
        existing_user = self.repository.get_by_email(user_create.email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError

        try:
            user = self.repository.create(
                email=user_create.email,
                full_name=user_create.full_name,
                hashed_password=hash_password(user_create.password),
                role=UserRole.PATIENT,
            )
        except IntegrityError as exc:
            # Concurrent registration with the same email won the race.
            self.repository.rollback()
            raise EmailAlreadyRegisteredError from exc

        if self.notification_service is not None:
            self.notification_service.record_registration_email(
                recipient_email=user.email,
                full_name=user.full_name,
            )

        self.repository.commit()
        return user

    def login(self, *, email: str, password: str) -> Token:
        user = self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError

        if not user.is_active:
            raise InactiveUserError

        return self.issue_token(user)

    def issue_token(self, user: User) -> Token:
        return Token(access_token=create_access_token(subject=user.id))

    def update_user_role(
        self,
        *,
        current_user: User,
        target_user_id: str,
        new_role: UserRole,
    ) -> User:
        target_user = self.repository.get_by_id(target_user_id)
        if target_user is None:
            raise UserNotFoundError

        current_role = UserRole(current_user.role)
        target_role = UserRole(target_user.role)
        allowed_target_roles = ROLE_CHANGE_RULES.get(current_role, {}).get(target_role)

        if allowed_target_roles is None or new_role not in allowed_target_roles:
            raise RoleChangeNotAllowedError

        target_user.role = new_role.value
        self.repository.commit()
        return target_user

    def ensure_base_admin(
        self,
        *,
        email: str,
        full_name: str,
        password: str,
    ) -> User:
        existing_user = self.repository.get_by_email(email)
        if existing_user is not None:
            return existing_user

        try:
            admin = self.repository.create(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(password),
                role=UserRole.ADMIN,
            )
            self.repository.commit()
        except IntegrityError:
            # Another worker seeded the admin concurrently.
            self.repository.rollback()
            existing_user = self.repository.get_by_email(email)
            if existing_user is None:
                raise
            return existing_user

        return admin
