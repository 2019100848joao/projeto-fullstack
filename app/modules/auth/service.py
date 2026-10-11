from app.core.security import create_access_token, hash_password, verify_password
from app.modules.auth.enums import UserRole
from app.modules.auth.exceptions import (
    EmailAlreadyRegisteredError,
    InactiveUserError,
    InvalidCredentialsError,
    RoleChangeNotAllowedError,
    UserNotFoundError,
)
from app.modules.auth.models import User
from app.modules.auth.permissions import PermissionService
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import Token, UserCreate


class AuthService:
    def __init__(
        self,
        repository: UserRepository,
        permissions: PermissionService | None = None,
    ) -> None:
        self.repository = repository
        self.permissions = permissions or PermissionService()

    def register(self, user_create: UserCreate) -> User:
        existing_user = self.repository.get_by_email(user_create.email)
        if existing_user is not None:
            raise EmailAlreadyRegisteredError

        return self.repository.create(
            email=user_create.email,
            full_name=user_create.full_name,
            hashed_password=hash_password(user_create.password),
            role=UserRole(user_create.role),
        )

    def login(self, *, email: str, password: str) -> Token:
        user = self.repository.get_by_email(email)
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError

        if not user.is_active:
            raise InactiveUserError

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

        if not self.permissions.can_change_user_role(
            current_user=current_user,
            target_user=target_user,
            new_role=new_role,
        ):
            raise RoleChangeNotAllowedError

        return self.repository.update_role(target_user, new_role)
