from sqlalchemy.exc import IntegrityError

from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    DoctorHasOpenWorkError,
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    LastAdminError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.schemas import Token, UserCreate
from app.modules.notifications.service import NotificationService
from app.modules.users.models import User
from app.modules.users.repository import UserRepository


def ensure_doctor_work_is_closed(
    repository: UserRepository,
    *,
    user: User,
    new_role: UserRole,
) -> None:
    """Only the requesting doctor can register an exam result, so a doctor who
    leaves the role with open work would leave it stuck forever."""
    if (
        user.role == UserRole.DOCTOR.value
        and new_role != UserRole.DOCTOR
        and repository.has_open_doctor_work(user.id)
    ):
        raise DoctorHasOpenWorkError


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
        # Any other role change goes through a role transition request, which
        # an admin approves, so direct changes are an admin decision only.
        if current_user.role != UserRole.ADMIN.value:
            raise RoleChangeNotAllowedError

        target_user = self.repository.get_by_id(target_user_id)
        if target_user is None:
            raise UserNotFoundError

        if target_user.role == UserRole.ADMIN.value and new_role != UserRole.ADMIN:
            other_admins = [
                admin_id
                for admin_id in self.repository.lock_active_admin_ids()
                if admin_id != target_user.id
            ]
            if not other_admins:
                raise LastAdminError

        ensure_doctor_work_is_closed(
            self.repository,
            user=target_user,
            new_role=new_role,
        )

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
